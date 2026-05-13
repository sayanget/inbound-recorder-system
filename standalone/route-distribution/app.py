"""
流向分布工具 — Standalone Executable
────────────────────────────────────────────────────────────
A self-contained local server that:
  • Serves the route-distribution dashboard HTML
  • Loads data either from
        (A) the main inbound API  (http://host:port)
     or (B) a Google Sheet CSV    (https://docs.google.com/spreadsheets/…)
  • Auto-opens the default browser on startup
  • Shows a simple status in the console window
  • Provides a /setup page where the user can switch data source any time

Build:  run  build.bat  (requires Python + pip install -r requirements.txt)
Run  :  double-click the generated .exe, or  `python app.py`

Config data source via any of (in priority order):
  1. Command line:  app.exe --backend <url>
  2. Env var     :  ROUTE_DIST_BACKEND=<url>
  3. config.txt  :  a file next to the .exe containing just the URL
                    (optional extra line  year=2026  for Sheet mode)
  4. Default     :  http://192.168.0.250:8080
  5. (runtime)   :  /setup page in the browser — user can change any
                    time; saves back into config.txt automatically.

Sheet-mode column mapping (per user spec, 1-indexed):
    B = DATE (MM-DD)        → record_date  (year inferred from query range)
    D = TO                  → route_code   (no merging, kept as-is upper)
    J = 价格                 → cost
    K = 发车运单号           → must start with "MT" to count as a trip,
                               otherwise the row is skipped (not yet dispatched)
    Each qualifying row contributes vehicle_count = 1.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import csv
import io
import ipaddress
import logging
import os
import re
import socket
import sys
import threading
import time
import webbrowser
from datetime import date, datetime, timedelta
from urllib.parse import urljoin, urlparse

from flask import Flask, Response, jsonify, request

try:
    import requests
except ImportError:  # pragma: no cover
    print("[!] 缺少依赖: requests\n请先执行: pip install -r requirements.txt")
    sys.exit(1)


DEFAULT_BACKEND = "http://192.168.0.250:8080"
APP_TITLE = "流向分布工具 (Route Distribution Tool)"
HTML_FILENAME = "route-distribution.html"

# Candidate ports to probe during LAN scan (default first)
SCAN_PORTS_DEFAULT = [8080, 80, 5000, 8000]
SCAN_TCP_TIMEOUT = 0.35   # seconds per TCP probe
SCAN_HTTP_TIMEOUT = 1.5   # seconds per HTTP verification probe

# Sheet mode constants
SHEET_HOSTS = ("docs.google.com", "sheets.google.com")
SHEET_MT_PREFIX = "MT"        # 发车运单号前缀
# Column lookup is done by header NAME (robust to column re-ordering in Sheets).
# Accepted header aliases — lower-cased & stripped before match.
SHEET_HDR_DATE = ("date", "日期")
SHEET_HDR_ROUTE = ("to", "流向", "目的地")
SHEET_HDR_COST = ("$", "cost", "price", "费用", "价格", "金额")
SHEET_HDR_MT = ("mt#", "mt #", "mt", "发车运单号", "运单号", "运单")
# Pickup# is used by the newer dispatch workflow (2026+) INSTEAD of MT#.
# Values look like 'LASCNO042618' = <DEST> + CNO + MMDD + seq — no year.
SHEET_HDR_PICKUP = ("pickup #", "pickup#", "pickup number", "pickup no", "pickup", "提货单号", "提货号")
SHEET_HTTP_TIMEOUT = 20
_sheet_cache: dict = {"key": None, "ts": 0.0, "rows": None}
SHEET_CACHE_TTL = 60          # seconds


# ---------------------------------------------------------------------------
# Resource resolution (works for dev run + PyInstaller --onefile)
# ---------------------------------------------------------------------------
def resource_path(rel: str) -> str:
    base = getattr(sys, "_MEIPASS", None)
    if not base:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, rel)


def route_distribution_html_path() -> str:
    """Frozen: bundled file. Dev: prefer repo static/ so 调度组模板与仓库一致."""
    if getattr(sys, "frozen", False):
        return resource_path(HTML_FILENAME)
    here = os.path.dirname(os.path.abspath(__file__))
    repo_static = os.path.normpath(os.path.join(here, "..", "..", "static", HTML_FILENAME))
    local = os.path.join(here, HTML_FILENAME)
    if os.path.isfile(repo_static):
        return repo_static
    if os.path.isfile(local):
        return local
    return local


def exe_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


# ---------------------------------------------------------------------------
# Backend URL resolution + live update
# ---------------------------------------------------------------------------
_backend_lock = threading.Lock()
_current_backend = ["", "", None]  # [backend, source_label, year_override]


def normalize_url(raw: str) -> str:
    raw = (raw or "").strip().rstrip("/")
    if not raw:
        return ""
    if not raw.startswith(("http://", "https://")):
        raw = "http://" + raw
    return raw


def is_sheet_url(url: str) -> bool:
    try:
        host = (urlparse(url).hostname or "").lower()
    except ValueError:
        return False
    return any(host == h or host.endswith("." + h) for h in SHEET_HOSTS)


def to_csv_export_url(url: str) -> str:
    """
    Accept any Google Sheet URL form (/edit#gid=0, /edit?gid=0, already /export,
    bare spreadsheet ID) and return the CSV export endpoint.
    """
    url = (url or "").strip()
    if not url:
        return ""
    # Bare ID (no slashes, typical length > 20)
    if "/" not in url and "." not in url and len(url) > 20:
        return f"https://docs.google.com/spreadsheets/d/{url}/export?format=csv&gid=0"
    m = re.search(r"/spreadsheets/d/([A-Za-z0-9_-]+)", url)
    if not m:
        return url  # fallback: hope the caller knew what they were doing
    sheet_id = m.group(1)
    # gid from either #gid=N or ?gid=N or &gid=N
    gm = re.search(r"[#?&]gid=(\d+)", url)
    gid = gm.group(1) if gm else "0"
    return f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}"


# ---- config.txt (supports single URL line or key=value lines) --------------
def _config_path() -> str:
    return os.path.join(exe_dir(), "config.txt")


def read_config() -> dict:
    """
    Returns dict with at least {"url": str}. Optional keys:
        year     -- int, default year for Sheet MM-DD dates
    Backwards compatible: a single URL line is accepted as-is.
    """
    path = _config_path()
    cfg: dict = {"url": "", "year": None}
    if not os.path.exists(path):
        return cfg
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = f.read()
    except OSError:
        return cfg
    lines = [ln.strip() for ln in raw.splitlines() if ln.strip() and not ln.strip().startswith("#")]
    if not lines:
        return cfg
    # If only URL form
    if "=" not in lines[0]:
        cfg["url"] = lines[0]
        for ln in lines[1:]:
            if "=" in ln:
                k, v = ln.split("=", 1)
                cfg[k.strip().lower()] = v.strip()
    else:
        for ln in lines:
            if "=" in ln:
                k, v = ln.split("=", 1)
                cfg[k.strip().lower()] = v.strip()
    # Coerce year to int
    try:
        cfg["year"] = int(cfg.get("year") or 0) or None
    except (TypeError, ValueError):
        cfg["year"] = None
    return cfg


def write_config(url: str, year: int | None = None) -> None:
    path = _config_path()
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(url + "\n")
            if year:
                f.write(f"year={year}\n")
    except OSError as e:
        print(f"[warn] 写入 config.txt 失败: {e}")


def resolve_backend_url(cli_value: str | None) -> tuple[str, str]:
    """Return (url, source_label)."""
    if cli_value:
        return normalize_url(cli_value), "命令行参数"
    env = os.environ.get("ROUTE_DIST_BACKEND", "").strip()
    if env:
        return normalize_url(env), "环境变量 ROUTE_DIST_BACKEND"
    cfg = read_config()
    if cfg.get("url"):
        return normalize_url(cfg["url"]), "config.txt"
    return DEFAULT_BACKEND, "内置默认值"


def save_config_file(url: str, year: int | None = None) -> None:
    write_config(url, year=year)


def get_backend() -> str:
    with _backend_lock:
        return _current_backend[0]


def get_backend_kind() -> str:
    """'sheet' or 'api' — computed from the stored URL."""
    return "sheet" if is_sheet_url(get_backend()) else "api"


def get_year_override() -> int | None:
    with _backend_lock:
        return _current_backend[2]


def set_backend(url: str, source: str = "用户设置", year: int | None = None, persist: bool = True) -> None:
    url = normalize_url(url)
    with _backend_lock:
        _current_backend[0] = url
        _current_backend[1] = source
        _current_backend[2] = year
    if persist:
        save_config_file(url, year=year)


def get_backend_source() -> str:
    with _backend_lock:
        return _current_backend[1]


# ---------------------------------------------------------------------------
# Google Sheet data source
# ---------------------------------------------------------------------------
def _parse_cost(raw: str) -> float:
    if raw is None:
        return 0.0
    s = str(raw).strip().replace(",", "").replace("$", "").replace("￥", "")
    if not s:
        return 0.0
    try:
        return float(s)
    except ValueError:
        # Ignore strings like "TBD", "pending", etc.
        return 0.0


_MT_YEAR_RE = re.compile(r"^\s*MT\s*([12]\d{3})(\d{2})(\d{2})", re.IGNORECASE)

# 固定甩挂/往返流向的关键词（匹配 TO 列原文，不区分大小写/全半角）。
# 这类班线是固定排班的 drop-trailer / 往返接驳，调度员惯例上不单独开 MT#
# 或 Pickup #，所以即使两列都空也应当算作已发车。
# 关键词：'drop trailer'（半角空格）、'droptrailer'、'drop-trailer'、以及
# 中文「往返」二字（全角或半角括号包围皆可）。
_DISPATCH_WAIVER_RE = re.compile(
    r"(drop\s*[- ]?\s*trailer|往返)",
    re.IGNORECASE,
)


def _is_dispatched(mt_cell: str, pickup_cell: str = "", route_cell: str = "") -> bool:
    """
    Strict rule (per user 2026-04-27): a row counts as dispatched ONLY when
    the MT# (K column) starts with 'MT' (case-insensitive).

    Pickup # 兜底 / drop-trailer 豁免这两条之前的兜底规则已停用——
    用户口径：只统计 MT 列实打实有 MT 编号的行。
    """
    mt = str(mt_cell or "").strip().upper()
    return mt.startswith(SHEET_MT_PREFIX)


def _year_from_mt(mt_cell: str) -> int | None:
    """
    Extract year from MT# of the form MT{YYYY}{MM}{DD}{serial}.
    This is the dispatch-date-encoded year assigned by the TMS and is the
    most reliable year signal in the sheet. Returns None if unparseable.
    """
    if not mt_cell:
        return None
    m = _MT_YEAR_RE.match(str(mt_cell).replace("\n", "").replace("\r", ""))
    if not m:
        return None
    y = int(m.group(1))
    if 2020 <= y <= 2099:
        return y
    return None


_DATE_FORMATS = ("%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y", "%m-%d-%Y", "%d/%m/%Y")


def _parse_sheet_date_parts(raw: str) -> tuple[int | None, int, int] | None:
    """
    Return (year_or_None, month, day) parsed from a sheet date cell.
    year is None when the cell is just MM-DD / M/D.
    """
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    for fmt in _DATE_FORMATS:
        try:
            d = datetime.strptime(s, fmt).date()
            return d.year, d.month, d.day
        except ValueError:
            pass
    m = re.match(r"^\s*(\d{1,2})[/\-](\d{1,2})\s*$", s)
    if not m:
        return None
    return None, int(m.group(1)), int(m.group(2))


def _assign_years_monotonic(
    parsed: list[tuple[int | None, int, int] | None],
    year_base: int,
    mt_hints: list[int | None] | None = None,
) -> list[str | None]:
    """
    Walk parsed dates in sheet order and assign ISO strings.

    Year inference order (strongest → weakest):
      1. Full date in the cell itself (YYYY-MM-DD etc.) sets year_cur.
      2. mt_hints[i] (year extracted from MT# prefix) sets year_cur.
      3. Monotonic rollover: if current MM-DD would land >180 days before
         the previous assigned date, bump year_cur by +1.

    year_cur initialised to year_base.
    """
    mt_hints = mt_hints or [None] * len(parsed)
    out: list[str | None] = []
    year_cur = year_base
    prev: date | None = None
    for p, mt_year in zip(parsed, mt_hints):
        if p is None:
            out.append(None)
            continue
        y, m, d = p
        if y is not None:
            # Explicit full date in cell — authoritative.
            try:
                cand = date(y, m, d)
            except ValueError:
                out.append(None)
                continue
            year_cur = y
        else:
            # No year in cell — prefer MT# hint, else fallback monotonic.
            if mt_year is not None:
                year_cur = mt_year
            try:
                cand = date(year_cur, m, d)
            except ValueError:
                out.append(None)
                continue
            if mt_year is None and prev is not None and (prev - cand).days > 180:
                year_cur += 1
                try:
                    cand = date(year_cur, m, d)
                except ValueError:
                    out.append(None)
                    continue
        prev = cand
        out.append(cand.strftime("%Y-%m-%d"))
    return out


def _match_header(cell: str, aliases: tuple[str, ...]) -> bool:
    s = (cell or "").strip().lower()
    if not s:
        return False
    for a in aliases:
        if s == a or s.startswith(a) or a in s:
            return True
    return False


def _find_header_row(rows: list[list[str]]) -> tuple[int, dict] | None:
    """
    Scan the first ~20 rows for one that contains all required headers:
        DATE, TO, $ (cost), MT#.
    Pickup # is optional (newer sheets use it; older ones don't have it).
    Return (row_index, {"date": idx, "route": idx, "cost": idx, "mt": idx,
                        "pickup": idx or -1}).
    """
    for i, row in enumerate(rows[:20]):
        found: dict = {}
        for j, cell in enumerate(row):
            # Pickup # is matched FIRST because its alias list shares the
            # token 'pickup' (not overlapping with MT#/date/etc).
            if "pickup" not in found and _match_header(cell, SHEET_HDR_PICKUP):
                found["pickup"] = j
            elif "date" not in found and _match_header(cell, SHEET_HDR_DATE):
                found["date"] = j
            elif "route" not in found and _match_header(cell, SHEET_HDR_ROUTE):
                found["route"] = j
            elif "mt" not in found and _match_header(cell, SHEET_HDR_MT):
                found["mt"] = j
            elif "cost" not in found and _match_header(cell, SHEET_HDR_COST):
                found["cost"] = j
        if {"date", "route", "cost", "mt"} <= set(found):
            found.setdefault("pickup", -1)  # -1 = not present in this sheet
            return i, found
    return None


def fetch_sheet_records(
    sheet_url: str,
    start_date: str | None = None,
    end_date: str | None = None,
    year_override: int | None = None,
) -> list[dict]:
    """
    Fetch the Google Sheet CSV export and transform it into the same shape the
    inbound API returns for /api/outbound/records:
        [{ "record_date": "YYYY-MM-DD",
           "route_code":   "<TO column raw>",
           "vehicle_count": 1,
           "cost":         <float> }, ...]
    Only rows where the MT# column starts with 'MT' are included.
    Columns are identified by HEADER NAME, so re-ordering the Sheet is OK.
    """
    csv_url = to_csv_export_url(sheet_url)
    now = time.time()
    cache_key = (csv_url, start_date, end_date, year_override)
    if (
        _sheet_cache.get("key") == cache_key
        and _sheet_cache.get("rows") is not None
        and now - _sheet_cache.get("ts", 0) < SHEET_CACHE_TTL
    ):
        return _sheet_cache["rows"]

    r = requests.get(csv_url, timeout=SHEET_HTTP_TIMEOUT, allow_redirects=True)
    if r.status_code != 200:
        raise RuntimeError(
            f"拉取 Google Sheet 失败 (HTTP {r.status_code})。"
            "请确认已设为「拥有链接的任何人 → 查看者」，且 URL 正确。"
        )
    # Google Sheets CSV export is ALWAYS UTF-8 (often with a BOM). Requests
    # sometimes auto-detects the encoding as ISO-8859-1 from an ambiguous
    # Content-Type header, which mojibakes Chinese cells like
    # 'LAV (往返）drop trailer'. Force UTF-8 and strip BOM.
    r.encoding = "utf-8-sig"
    reader = csv.reader(io.StringIO(r.text))
    all_rows = list(reader)

    hdr = _find_header_row(all_rows)
    if not hdr:
        raise RuntimeError(
            "在 Google Sheet 前 20 行未找到所需表头 (需要同时包含 DATE / TO / $ / MT#)。"
            "请检查 Sheet 结构，或在 gid 指向的工作表是否为正确的那张表。"
        )
    hdr_row, col = hdr
    c_date, c_route, c_cost, c_mt = col["date"], col["route"], col["cost"], col["mt"]
    c_pickup = col.get("pickup", -1)

    # MT column resolution. Per user 2026-04-27 ("只统计 K"), the canonical
    # MT-number column is the un-headed column the dispatch team writes into
    # for the current workflow era. In the live 2026 sheet that's column K
    # (idx 10) — the column literally labelled "MT#" (idx 12) is filled only
    # for legacy rows and is ignored here.
    #
    # Strategy:
    #   1. Scan every non-key column for "MT##...##" density.
    #   2. Among columns whose HEADER is blank, take the one with the most
    #      MT-prefix hits — that's column K.
    #   3. If no blank-header column has any hits, fall back to the
    #      header-matched MT# column for backward compat with old sheets.
    body_rows = all_rows[hdr_row + 1 :]
    header_cells = all_rows[hdr_row] if hdr_row < len(all_rows) else []

    def _mt_hit_count(idx: int) -> int:
        if idx < 0:
            return 0
        n = 0
        for r in body_rows:
            if idx < len(r) and str(r[idx]).strip().upper().startswith(SHEET_MT_PREFIX):
                n += 1
        return n

    def _header_blank(idx: int) -> bool:
        return idx >= len(header_cells) or not str(header_cells[idx]).strip()

    max_col = max((len(r) for r in body_rows), default=c_mt + 1)
    blank_candidate, blank_best_hits = -1, 0
    for j in range(max_col):
        if j in (c_date, c_route, c_cost, c_pickup):
            continue
        if not _header_blank(j):
            continue
        h = _mt_hit_count(j)
        if h > blank_best_hits:
            blank_candidate, blank_best_hits = j, h

    if blank_candidate >= 0 and blank_best_hits > 0:
        c_mt = blank_candidate

    max_idx = max(c_date, c_route, c_cost, c_mt, c_pickup if c_pickup >= 0 else 0)

    # Decide year_base used by the monotonic walker.
    # Priority: explicit override > start_date's year > current year.
    year_base = (
        int(year_override)
        if year_override
        else (datetime.strptime(start_date, "%Y-%m-%d").year if start_date else datetime.now().year)
    )

    # Pass 1: parse every row's date cell & collect MT# year hints
    parsed_all: list[tuple[int | None, int, int] | None] = []
    mt_year_hints: list[int | None] = []
    raw_rows: list[list[str]] = []
    for row in all_rows[hdr_row + 1:]:
        if len(row) <= max_idx:
            row = list(row) + [""] * (max_idx - len(row) + 1)
        raw_rows.append(row)
        parsed_all.append(_parse_sheet_date_parts(row[c_date]))
        mt_year_hints.append(_year_from_mt(row[c_mt]))

    # Pass 2: assign ISO dates (MT# hints override, monotonic rollover fallback)
    iso_dates = _assign_years_monotonic(parsed_all, year_base, mt_year_hints)

    records: list[dict] = []
    for row, iso in zip(raw_rows, iso_dates):
        if not iso:
            continue
        route = (row[c_route] or "").strip()
        if not route:
            continue  # TO 空的行一律跳过
        pickup_val = row[c_pickup] if c_pickup >= 0 else ""
        if not _is_dispatched(row[c_mt], pickup_val, route):
            continue
        records.append({
            "record_date": iso,
            "route_code": route,
            "vehicle_count": 1,
            "cost": _parse_cost(row[c_cost]),
        })

    if start_date:
        records = [rec for rec in records if rec["record_date"] >= start_date]
    if end_date:
        records = [rec for rec in records if rec["record_date"] <= end_date]

    _sheet_cache.update({"key": cache_key, "ts": now, "rows": records})
    return records


def invalidate_sheet_cache() -> None:
    _sheet_cache.update({"key": None, "ts": 0.0, "rows": None})


# ---------------------------------------------------------------------------
# Probe utilities — quickly check whether a backend is reachable & is ours
# ---------------------------------------------------------------------------
def tcp_alive(host: str, port: int, timeout: float = SCAN_TCP_TIMEOUT) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def probe_backend(url: str, timeout: float = SCAN_HTTP_TIMEOUT) -> dict:
    """
    Return { ok, status, is_inbound_app, kind, message }.
    * kind='sheet' → tries Google CSV export.
    * kind='api'   → TCP + GET /api/outbound/records.
    """
    url = normalize_url(url)
    if not url:
        return {"ok": False, "kind": None, "message": "URL 为空"}

    # ---- Sheet mode ----
    if is_sheet_url(url):
        csv_url = to_csv_export_url(url)
        try:
            r = requests.get(csv_url, timeout=timeout, allow_redirects=True)
        except requests.exceptions.RequestException as e:
            return {"ok": False, "kind": "sheet", "message": f"抓取失败: {e}"}
        ct = (r.headers.get("Content-Type") or "").lower()
        body_peek = (r.text or "")[:256].lower() if r.status_code == 200 else ""
        looks_html_login = "google accounts" in body_peek or "<!doctype html" in body_peek
        ok = r.status_code == 200 and ("csv" in ct or "text/plain" in ct or r.text.count(",") > 5)
        msg = (
            f"HTTP {r.status_code}"
            + ("（疑似未公开：返回的是登录页）" if looks_html_login else "")
        )
        return {
            "ok": bool(ok) and not looks_html_login,
            "kind": "sheet",
            "status": r.status_code,
            "is_inbound_app": bool(ok) and not looks_html_login,
            "content_type": ct,
            "message": msg,
            "csv_url": csv_url,
        }

    # ---- API mode (original logic) ----
    parsed = urlparse(url)
    host, port = parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80)
    if not host:
        return {"ok": False, "kind": "api", "message": f"URL 格式错误: {url}"}

    if not tcp_alive(host, port, timeout=min(timeout, 1.5)):
        return {"ok": False, "kind": "api", "message": f"TCP 不通 ({host}:{port})"}

    probe_url = urljoin(url + "/", "api/outbound/records")
    today = time.strftime("%Y-%m-%d")
    try:
        r = requests.get(
            probe_url,
            params={"start_date": today, "end_date": today, "limit": 1},
            timeout=timeout,
        )
    except requests.exceptions.RequestException as e:
        return {"ok": False, "kind": "api", "message": f"HTTP 请求异常: {e}"}

    ct = (r.headers.get("Content-Type") or "").lower()
    try:
        body = r.json() if "json" in ct else None
    except ValueError:
        body = None

    is_app = False
    if isinstance(body, dict):
        keys = set(body.keys())
        if keys & {"records", "data", "total", "success"}:
            is_app = True
    elif isinstance(body, list):
        is_app = True

    return {
        "ok": r.status_code < 500,
        "kind": "api",
        "status": r.status_code,
        "is_inbound_app": is_app,
        "content_type": ct,
        "message": f"HTTP {r.status_code}" + ("" if is_app else "（响应不像出库系统）"),
    }


# ---------------------------------------------------------------------------
# LAN discovery — scan local /24 subnets for a reachable backend
# ---------------------------------------------------------------------------
def local_ipv4_addresses() -> list[str]:
    """Best-effort list of this host's LAN IPv4 addresses."""
    out: set[str] = set()
    try:
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None, socket.AF_INET):
            ip = info[4][0]
            if ip and not ip.startswith("127."):
                out.add(ip)
    except socket.gaierror:
        pass
    # Fallback: connect-to-outside trick to learn default-interface IP
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("8.8.8.8", 80))
            out.add(s.getsockname()[0])
        finally:
            s.close()
    except OSError:
        pass
    return sorted(out)


def subnets_for_scan() -> list[ipaddress.IPv4Network]:
    nets: list[ipaddress.IPv4Network] = []
    seen: set[str] = set()
    for ip in local_ipv4_addresses():
        try:
            net = ipaddress.IPv4Network(ip + "/24", strict=False)
        except ValueError:
            continue
        if str(net) in seen:
            continue
        seen.add(str(net))
        nets.append(net)
    return nets


def lan_scan(
    ports: list[int] | None = None,
    max_workers: int = 128,
    on_progress=None,
) -> list[dict]:
    """
    Scan all /24 subnets of local interfaces for open `ports`.
    Returns a list of candidates:
        [{ "url": "http://ip:port", "tcp": True, "is_inbound_app": bool, ... }]
    """
    ports = ports or SCAN_PORTS_DEFAULT
    nets = subnets_for_scan()
    if not nets:
        return []

    targets: list[tuple[str, int]] = []
    for net in nets:
        # Skip .0 (network) and .255 (broadcast); 254 hosts each
        for host_ip in net.hosts():
            for p in ports:
                targets.append((str(host_ip), p))

    hits_tcp: list[tuple[str, int]] = []
    scanned = 0
    total = len(targets)

    def _probe_one(addr):
        host, port = addr
        return addr if tcp_alive(host, port) else None

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
        for res in pool.map(_probe_one, targets, chunksize=8):
            scanned += 1
            if res is not None:
                hits_tcp.append(res)
            if on_progress and scanned % 50 == 0:
                on_progress(scanned, total)

    # Second pass: HTTP-probe each TCP hit to see if it's our app
    results: list[dict] = []
    for host, port in hits_tcp:
        url = f"http://{host}:{port}"
        info = probe_backend(url, timeout=1.2)
        results.append(
            {
                "url": url,
                "host": host,
                "port": port,
                "tcp": True,
                "ok": bool(info.get("ok")),
                "is_inbound_app": bool(info.get("is_inbound_app")),
                "status": info.get("status"),
                "message": info.get("message"),
            }
        )
    # Prefer our-app hits first, then other-reachable, then rest
    results.sort(
        key=lambda r: (
            not r["is_inbound_app"],
            not r["ok"],
            r["host"],
            r["port"],
        )
    )
    return results


# ---------------------------------------------------------------------------
# Free port finder
# ---------------------------------------------------------------------------
def find_free_port(preferred: int = 9090) -> int:
    for port in (preferred, *range(9090, 9210)):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise RuntimeError("No free port found in 9090-9209")


# ---------------------------------------------------------------------------
# Setup page HTML (inline; no external file)
# ---------------------------------------------------------------------------
SETUP_HTML = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>设置数据源 | 流向分布工具</title>
<style>
:root{--bg:#0f172a;--card:#1e293b;--border:#334155;--text:#e2e8f0;--muted:#94a3b8;
--accent:#3b82f6;--ok:#22c55e;--warn:#f59e0b;--err:#ef4444;}
*{box-sizing:border-box}
body{margin:0;padding:24px;font-family:-apple-system,"Segoe UI",sans-serif;
background:var(--bg);color:var(--text);line-height:1.55}
.wrap{max-width:840px;margin:0 auto}
h1{font-size:22px;margin:0 0 4px}
.sub{color:var(--muted);margin-bottom:20px;font-size:14px}
.card{background:var(--card);border:1px solid var(--border);border-radius:8px;
padding:18px;margin-bottom:16px}
.row{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
input[type=text]{flex:1;min-width:240px;padding:8px 10px;border-radius:6px;
border:1px solid var(--border);background:#0b1221;color:var(--text);font:14px monospace}
button{padding:8px 14px;border-radius:6px;border:1px solid var(--border);
background:#334155;color:var(--text);cursor:pointer;font-size:14px}
button:hover{background:#475569}
button.primary{background:var(--accent);border-color:var(--accent)}
button.primary:hover{background:#2563eb}
button.ok{background:var(--ok);border-color:var(--ok)}
button:disabled{opacity:.5;cursor:not-allowed}
.badge{display:inline-block;padding:2px 8px;border-radius:10px;font-size:11px;
font-weight:600;margin-left:6px}
.badge.ok{background:var(--ok);color:#0b1221}
.badge.warn{background:var(--warn);color:#0b1221}
.badge.err{background:var(--err);color:#fff}
.msg{margin-top:10px;font-size:13px;color:var(--muted)}
.msg.ok{color:var(--ok)} .msg.err{color:var(--err)}
table{width:100%;border-collapse:collapse;margin-top:10px;font-size:13px}
th,td{text-align:left;padding:8px;border-bottom:1px solid var(--border)}
tr.app td{background:rgba(34,197,94,.08)}
small{color:var(--muted)}
kbd{padding:1px 6px;border-radius:4px;background:#334155;border:1px solid #475569;
font:12px monospace}
.hint{font-size:12px;color:var(--muted);margin-top:6px}
</style>
</head>
<body>
<div class="wrap">

<h1>设置数据源</h1>
<div class="sub">
  当前使用:
  <span id="curKind" class="badge"></span>
  <code id="cur"></code>
  <span id="curSrc" class="badge"></span>
</div>

<div class="card">
  <strong>选择数据源类型</strong>
  <div class="row" style="margin-top:8px;gap:14px">
    <label><input type="radio" name="kind" value="api"> 出库 API</label>
    <label><input type="radio" name="kind" value="sheet"> Google Sheet (CSV)</label>
  </div>
  <div class="hint" id="kindHint">
    根据你填写的 URL 自动识别；也可手动切换。
  </div>
</div>

<div class="card">
  <strong>数据源地址</strong>
  <div class="row" style="margin-top:8px">
    <input id="urlInput" type="text" placeholder="http://192.168.0.xxx:8080  或  https://docs.google.com/spreadsheets/d/...">
    <button id="btnTest">测试连接</button>
    <button id="btnSave" class="primary">保存并启用</button>
  </div>
  <div class="hint" id="urlHint"></div>
  <div id="sheetOpts" style="display:none;margin-top:10px">
    <div class="row">
      <label>MM-DD 日期默认年份:
        <input id="yearInput" type="number" min="2000" max="2100" style="width:90px;padding:4px 6px"
               placeholder="2026">
      </label>
      <small>仅当 Sheet 中日期是 "MM-DD" 时用于补全年份。空 = 跟随查询日期年份。</small>
    </div>
  </div>
  <div id="testMsg" class="msg"></div>
</div>

<div class="card" id="lanCard">
  <div class="row" style="justify-content:space-between">
    <strong>局域网自动扫描 (仅 API 模式)</strong>
    <div class="row">
      <button id="btnScan" class="primary">开始扫描</button>
    </div>
  </div>
  <div class="hint">
    扫描本机所在的 /24 子网，探测 8080 / 80 / 5000 / 8000 端口。
    深绿色背景的行表示确认是出库系统（/api/outbound/records 响应正常）。
  </div>
  <div id="scanMsg" class="msg"></div>
  <table id="scanTable" style="display:none">
    <thead><tr>
      <th>地址</th><th>端口</th><th>状态</th><th>识别</th><th></th>
    </tr></thead>
    <tbody></tbody>
  </table>
</div>

<div class="card">
  <strong>或者直接进入应用</strong>
  <div class="hint">
    如果你已经知道当前数据源可用，可直接 <a href="/" style="color:var(--accent)">返回主页</a>；
    应用内也能随时点击顶部 <kbd>⚙ 数据源</kbd> 回到本页。
  </div>
</div>

<div class="sub" style="margin-top:24px;font-size:12px">
  说明 / 提示:<br>
  • <b>Google Sheet 模式</b>：Sheet 必须设为「拥有链接的任何人 → 查看者」。工具按列解析:
    <code>B=DATE</code>, <code>D=TO</code>, <code>J=价格</code>, <code>K=MT#</code>;
    K 列未以 "MT" 开头的行视为未发车，自动跳过。<br>
  • <b>API 模式</b>：填 <code>http://host:port</code>。若后端机 IP 固定，推荐用主机名。<br>
  • 批量改：覆盖 exe 同目录的 <code>config.txt</code>（第一行 URL，可加 <code>year=2026</code>）
</div>

</div>
<script>
const $ = s => document.querySelector(s);
const cur = $('#cur'), curSrc = $('#curSrc'), curKind = $('#curKind');
const urlInput = $('#urlInput');
const yearInput = $('#yearInput');
const sheetOpts = $('#sheetOpts');
const lanCard = $('#lanCard');
const urlHint = $('#urlHint');

function detectKind(url){
  const u = (url||'').toLowerCase();
  if(u.includes('docs.google.com') || u.includes('sheets.google.com')) return 'sheet';
  if(u.startsWith('http')) return 'api';
  return '';
}

function setRadio(kind){
  document.querySelectorAll('input[name=kind]').forEach(r => r.checked = (r.value === kind));
}

function applyKindUI(kind){
  if(kind === 'sheet'){
    sheetOpts.style.display = '';
    lanCard.style.display = 'none';
    urlHint.textContent = '粘贴 Sheet URL（/edit#gid=0 或任意格式均可），会自动转为 CSV 导出地址。';
  } else {
    sheetOpts.style.display = 'none';
    lanCard.style.display = '';
    urlHint.textContent = '支持 IP 或主机名（如 http://server01:8080），末尾 "/" 可省略。';
  }
}

urlInput.addEventListener('input', ()=>{
  const k = detectKind(urlInput.value.trim());
  if(k){ setRadio(k); applyKindUI(k); }
});

document.querySelectorAll('input[name=kind]').forEach(r =>
  r.addEventListener('change', ()=> applyKindUI(r.value))
);

async function refreshCurrent(){
  const r = await fetch('/api/current-backend').then(r=>r.json()).catch(()=>null);
  if(!r) return;
  cur.textContent = r.backend || '(未设置)';
  curSrc.textContent = r.source || '';
  curSrc.className = 'badge ' + (r.reachable ? 'ok' : 'err');
  curSrc.title = r.reachable ? '可达' : '不可达';
  const k = r.kind || detectKind(r.backend);
  curKind.textContent = (k === 'sheet') ? 'Google Sheet' : 'API';
  curKind.className = 'badge ' + (k === 'sheet' ? 'warn' : 'ok');
  setRadio(k); applyKindUI(k);
  if(!urlInput.value) urlInput.value = r.backend || '';
  if(r.year && !yearInput.value) yearInput.value = r.year;
}
refreshCurrent();

$('#btnTest').addEventListener('click', async ()=>{
  const url = urlInput.value.trim();
  if(!url){ alert('先填一个 URL'); return; }
  const m = $('#testMsg');
  m.className='msg'; m.textContent='测试中...';
  try{
    const r = await fetch('/api/probe?url='+encodeURIComponent(url)).then(r=>r.json());
    if(r.ok && r.kind === 'sheet'){
      m.className='msg ok'; m.textContent='✓ Google Sheet CSV 可读 (HTTP '+r.status+')';
    } else if(r.ok && r.is_inbound_app){
      m.className='msg ok'; m.textContent='✓ 连通，且确认是出库系统 (HTTP '+r.status+')';
    } else if(r.ok){
      m.className='msg'; m.textContent='△ 连通但响应不像预期 ('+(r.message||'')+')';
    } else {
      m.className='msg err'; m.textContent='✗ '+(r.message||'不可达');
    }
  }catch(e){
    m.className='msg err'; m.textContent='✗ '+e;
  }
});

$('#btnSave').addEventListener('click', async ()=>{
  const url = urlInput.value.trim();
  if(!url){ alert('先填一个 URL'); return; }
  const payload = { url };
  if(yearInput.value && detectKind(url) === 'sheet'){
    payload.year = parseInt(yearInput.value, 10) || null;
  }
  const r = await fetch('/api/set-backend', {
    method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify(payload)
  }).then(r=>r.json()).catch(e=>({ok:false,error:String(e)}));
  if(r.ok){
    $('#testMsg').className='msg ok';
    $('#testMsg').textContent='✓ 已保存 (' + (r.kind === 'sheet' ? 'Google Sheet' : 'API') + ')。即将跳转到主页…';
    setTimeout(()=>{location.href='/';}, 800);
  } else {
    $('#testMsg').className='msg err';
    $('#testMsg').textContent='✗ 保存失败: '+(r.error||'');
  }
});

$('#btnScan').addEventListener('click', async ()=>{
  const btn = $('#btnScan'); btn.disabled = true;
  const m = $('#scanMsg'); m.className='msg'; m.textContent='正在扫描本机所在子网…通常 10~30 秒';
  const table = $('#scanTable'); table.style.display='none';
  const tbody = table.querySelector('tbody'); tbody.innerHTML='';
  try{
    const r = await fetch('/api/lan-scan').then(r=>r.json());
    if(!r.results || !r.results.length){
      m.className='msg'; m.textContent='未发现监听目标端口的主机。请手动输入。';
      btn.disabled=false; return;
    }
    m.className='msg ok'; m.textContent='扫描完成，共 '+r.results.length+' 个候选。';
    table.style.display='';
    for(const c of r.results){
      const tr = document.createElement('tr');
      if(c.is_inbound_app) tr.classList.add('app');
      tr.innerHTML =
        '<td><code>'+c.host+'</code></td>'+
        '<td>'+c.port+'</td>'+
        '<td>'+(c.ok?'HTTP '+c.status:'TCP 通，HTTP 异常')+'</td>'+
        '<td>'+(c.is_inbound_app?'<span class="badge ok">出库系统</span>':'<span class="badge warn">其他服务</span>')+'</td>'+
        '<td><button data-url="'+c.url+'" class="use primary">使用</button></td>';
      tbody.appendChild(tr);
    }
    tbody.querySelectorAll('.use').forEach(b=>{
      b.addEventListener('click', async ()=>{
        urlInput.value = b.dataset.url;
        $('#btnSave').click();
      });
    });
  }catch(e){
    m.className='msg err'; m.textContent='扫描失败: '+e;
  }finally{ btn.disabled=false; }
});
</script>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Flask app
# ---------------------------------------------------------------------------
def build_app() -> Flask:
    app = Flask(__name__)
    logging.getLogger("werkzeug").setLevel(logging.WARNING)

    html_path = route_distribution_html_path()
    if not os.path.exists(html_path):
        raise FileNotFoundError(
            f"找不到 {HTML_FILENAME}：试过仓库 static/ 与同目录，请检查路径或重新从 static 复制"
        )

    def _load_html() -> str:
        """
        Re-read route-distribution.html from disk on every main-page request.
        Previously we cached the file contents once at process start, which
        meant editing the HTML required a server restart to take effect — a
        common source of "我改了怎么没生效" confusion during development.
        The re-read cost (~1 ms for a ~60 KB file on warm FS cache) is
        negligible compared to the data-loading round-trip.
        """
        with open(html_path, "r", encoding="utf-8") as f:
            return f.read()

    def render_main_html() -> str:
        backend = get_backend()
        kind = get_backend_kind()
        label = "Google Sheet" if kind == "sheet" else "API"
        # Trim super-long sheet URLs for the chip
        display = backend if len(backend) <= 60 else backend[:28] + "…" + backend[-28:]
        h = _load_html()
        h = h.replace(
            '<a href="/outbound-stats" class="back-link">← 返回出库统计</a>',
            f'<a href="/setup" class="back-link" '
            f'title="点击切换数据源（API / Google Sheet）" '
            f'style="font-size:12px;color:var(--muted);text-decoration:none;">'
            f'⚙ 数据源 [{label}]: {display}</a>',
        )
        h = h.replace(
            "<title>流向分布数据表 | Route Distribution</title>",
            f"<title>{APP_TITLE}</title>",
        )
        return h

    @app.after_request
    def _permissions_policy_header(response):
        # 显式允许 unload，避免 Chrome 对任何页面上 addEventListener('unload',…) 的调用
        # 抛出 "[Violation] Permissions policy violation: unload is not allowed in this document."
        # (某些浏览器扩展注入的 index.global.js 会触发该告警)
        response.headers.setdefault("Permissions-Policy", "unload=*")
        return response

    @app.route("/")
    def index():
        return render_main_html(), 200, {"Content-Type": "text/html; charset=utf-8"}

    @app.route("/setup")
    def setup():
        return SETUP_HTML, 200, {"Content-Type": "text/html; charset=utf-8"}

    @app.route("/health")
    def health():
        return jsonify({"ok": True, "backend": get_backend()})

    # Serve an inline SVG favicon so the browser stops spamming 404s to
    # /favicon.ico. The emoji matches the ⚙ theme used in the header.
    @app.route("/favicon.ico")
    @app.route("/favicon.svg")
    def favicon():
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">'
            '<rect width="64" height="64" rx="12" fill="#2563eb"/>'
            '<text x="50%" y="54%" text-anchor="middle" '
            'dominant-baseline="middle" font-size="40" '
            'font-family="Segoe UI Emoji, Apple Color Emoji, sans-serif" '
            'fill="#fff">⚙</text></svg>'
        )
        return svg, 200, {
            "Content-Type": "image/svg+xml",
            "Cache-Control": "public, max-age=86400",
        }

    # ------------------- Runtime config endpoints -------------------
    @app.route("/api/current-backend", methods=["GET"])
    def current_backend():
        url = get_backend()
        info = probe_backend(url, timeout=1.5) if url else {"ok": False}
        return jsonify(
            {
                "backend": url,
                "source": get_backend_source(),
                "kind": get_backend_kind(),
                "year": get_year_override(),
                "reachable": bool(info.get("ok")),
                "is_inbound_app": bool(info.get("is_inbound_app")),
            }
        )

    @app.route("/api/probe", methods=["GET"])
    def probe():
        url = request.args.get("url", "")
        return jsonify(probe_backend(url))

    @app.route("/api/set-backend", methods=["POST"])
    def set_backend_endpoint():
        data = request.get_json(silent=True) or {}
        url = normalize_url(data.get("url", ""))
        if not url:
            return jsonify({"ok": False, "error": "URL 为空"}), 400
        year = data.get("year")
        try:
            year_int = int(year) if year not in (None, "", 0, "0") else None
        except (TypeError, ValueError):
            year_int = None
        info = probe_backend(url)
        if not info.get("ok"):
            return jsonify({"ok": False, "error": info.get("message", "不可达")}), 400
        set_backend(url, source="设置页", year=year_int)
        invalidate_sheet_cache()
        return jsonify({"ok": True, "backend": url, "kind": info.get("kind"), "probe": info})

    @app.route("/api/lan-scan", methods=["GET"])
    def api_scan():
        ports = request.args.get("ports")
        port_list = SCAN_PORTS_DEFAULT
        if ports:
            try:
                port_list = [int(x) for x in ports.split(",") if x.strip()]
            except ValueError:
                pass
        results = lan_scan(ports=port_list)
        return jsonify({"results": results, "scanned_subnets": [str(n) for n in subnets_for_scan()]})

    # ------------------- Data source -------------------
    @app.route("/api/outbound/records", methods=["GET"])
    def records():
        backend = get_backend()
        start = request.args.get("start_date")
        end = request.args.get("end_date")

        # ---- Sheet mode ----
        if is_sheet_url(backend):
            try:
                recs = fetch_sheet_records(
                    backend,
                    start_date=start,
                    end_date=end,
                    year_override=get_year_override(),
                )
            except requests.exceptions.RequestException as e:
                return jsonify({
                    "error": f"Google Sheet 抓取失败: {e}",
                    "backend": backend,
                }), 502
            except Exception as e:
                return jsonify({"error": str(e), "backend": backend}), 502
            return jsonify(recs)

        # ---- API mode ----
        target = urljoin(backend + "/", "api/outbound/records")
        try:
            r = requests.get(target, params=request.args.to_dict(flat=True), timeout=30)
        except requests.exceptions.ConnectTimeout:
            return jsonify({
                "error": (
                    f"连接超时：{target}。可能后端 IP 已变更，"
                    "请点页面顶部 [⚙ 数据源] 重新设置。"
                ),
                "backend": backend,
            }), 504
        except requests.exceptions.ConnectionError as e:
            return jsonify({
                "error": (
                    f"无法连接到后端 {backend}: {e}。"
                    "如果后端 IP 变了，请打开 /setup 重新设置。"
                ),
                "backend": backend,
            }), 502
        except requests.exceptions.RequestException as e:
            return jsonify({"error": f"请求失败: {e}", "backend": backend}), 502
        ct = r.headers.get("Content-Type", "application/json")
        return Response(r.content, status=r.status_code, content_type=ct)

    @app.route("/api/refresh", methods=["POST"])
    def refresh_sheet():
        invalidate_sheet_cache()
        return jsonify({"ok": True})

    return app


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def banner(backend: str, port: int, reachable: bool, source: str) -> None:
    ok_mark = "[OK]" if reachable else "[!!]"
    kind_label = "Google Sheet" if is_sheet_url(backend) else "API"
    print("=" * 64)
    print(f"  {APP_TITLE}")
    print("=" * 64)
    print(f"  本地地址    : http://127.0.0.1:{port}/")
    print(f"  数据源类型  : {kind_label}")
    print(f"  数据源 URL  : {backend}  [{source}]")
    print(f"  可达性      : {ok_mark} {'已连通' if reachable else '不可达（将跳转设置页）'}")
    print(f"  配置文件    : {os.path.join(exe_dir(), 'config.txt')}")
    print("=" * 64)
    if reachable:
        print("  浏览器将在 2 秒后自动打开主页…")
    else:
        print("  ! 后端不可达 —— 浏览器将打开设置页，可填 IP 或一键扫描局域网")
    print("  关闭本窗口即停止服务（Ctrl+C 亦可）")
    print("=" * 64)


def main(argv=None):
    # Force stdout/stderr to UTF-8 so Chinese banner prints correctly even on
    # Windows consoles running under GBK (cp936).
    try:
        sys.stdout.reconfigure(encoding="utf-8")      # type: ignore[attr-defined]
        sys.stderr.reconfigure(encoding="utf-8")      # type: ignore[attr-defined]
    except Exception:
        pass

    parser = argparse.ArgumentParser(description=APP_TITLE)
    parser.add_argument("--backend", help="Backend URL, e.g. http://192.168.0.250:8080")
    parser.add_argument("--port", type=int, default=9090, help="Preferred local port")
    parser.add_argument("--no-browser", action="store_true", help="Don't auto-open browser")
    parser.add_argument("--skip-probe", action="store_true", help="Skip startup backend probe")
    args = parser.parse_args(argv)

    backend, source = resolve_backend_url(args.backend)
    year_init = read_config().get("year")
    # Don't overwrite existing config.txt on startup (persist=False); only /setup saves.
    set_backend(backend, source=source, year=year_init, persist=False)

    # Startup probe — decide whether to land on / or /setup
    reachable = True
    if not args.skip_probe:
        info = probe_backend(backend, timeout=2.0)
        reachable = bool(info.get("ok"))

    try:
        app = build_app()
    except FileNotFoundError as e:
        print(f"[启动失败] {e}")
        input("\n按回车键退出…")
        sys.exit(1)

    port = find_free_port(args.port)
    banner(backend, port, reachable, source)

    if not args.no_browser:
        landing = "/" if reachable else "/setup"
        threading.Timer(
            2.0, lambda: webbrowser.open(f"http://127.0.0.1:{port}{landing}")
        ).start()

    try:
        app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False, threaded=True)
    except KeyboardInterrupt:
        print("\n已停止。")
    except Exception as e:  # pragma: no cover
        print(f"[运行异常] {e}")
        input("\n按回车键退出…")
        sys.exit(1)


if __name__ == "__main__":
    main()
