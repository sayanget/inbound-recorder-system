"""
流向分布 — 复用 standalone/route-distribution 的数据源方案（API / Google Sheet）。
配置持久化在 system_config（route_dist_backend / route_dist_year / route_dist_source）。
"""
from __future__ import annotations

import importlib.util
import os
import threading
from urllib.parse import urljoin, urlparse

import requests

_hooks: dict = {}
_lock = threading.Lock()
_cache = {"loaded": False, "backend": "", "source": "", "year": None}

CFG_BACKEND = "route_dist_backend"
CFG_YEAR = "route_dist_year"
CFG_SOURCE = "route_dist_source"

DEFAULT_SHEET_URL = (
    "https://docs.google.com/spreadsheets/d/"
    "1sEjOb1Yy7ap_B6LpHNHxIgF21vzDCvD1uSqSBIY9oTA/edit?gid=0#gid=0"
)

_rd_mod = None


def _standalone_module():
    global _rd_mod
    if _rd_mod is not None:
        return _rd_mod
    here = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(here, "standalone", "route-distribution", "app.py")
    spec = importlib.util.spec_from_file_location("route_dist_standalone", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    _rd_mod = mod
    return mod


def configure(get_db, convert_query_placeholders, fetch_local_records, use_postgres=False):
    _hooks["get_db"] = get_db
    _hooks["convert"] = convert_query_placeholders
    _hooks["fetch_local_records"] = fetch_local_records
    _hooks["use_postgres"] = use_postgres


def _config_txt_default() -> tuple[str, int | None]:
    here = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(here, "standalone", "route-distribution", "config.txt")
    if not os.path.isfile(path):
        return DEFAULT_SHEET_URL, None
    try:
        cfg = _standalone_module().read_config()
        url = (cfg.get("url") or "").strip()
        year = cfg.get("year")
        if url:
            return url, year
    except Exception:
        pass
    return DEFAULT_SHEET_URL, None


def _read_db_config() -> tuple[str, str, int | None]:
    get_db = _hooks.get("get_db")
    convert = _hooks.get("convert")
    if not get_db or not convert:
        return "", "", None
    conn = get_db()
    try:
        cur = conn.cursor()
        out = {}
        for key in (CFG_BACKEND, CFG_YEAR, CFG_SOURCE):
            cur.execute(convert("SELECT config_value FROM system_config WHERE config_key = ?"), (key,))
            row = cur.fetchone()
            if row is None:
                out[key] = ""
            elif isinstance(row, dict):
                out[key] = row.get("config_value") or ""
            else:
                out[key] = row[0] or ""
        year = None
        try:
            year = int(out.get(CFG_YEAR) or 0) or None
        except (TypeError, ValueError):
            year = None
        return out.get(CFG_BACKEND) or "", out.get(CFG_SOURCE) or "", year
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _write_db_config(url: str, source: str, year: int | None) -> None:
    get_db = _hooks["get_db"]
    convert = _hooks["convert"]
    conn = get_db()
    try:
        cur = conn.cursor()
        rows = [
            (CFG_BACKEND, url, "流向分布数据源 URL（API 或 Google Sheet）"),
            (CFG_SOURCE, source, "流向分布数据源来源说明"),
            (CFG_YEAR, str(year) if year else "", "Sheet 模式 MM-DD 默认年份"),
        ]
        use_pg = _hooks.get("use_postgres")
        for key, val, desc in rows:
            if use_pg:
                cur.execute(
                    convert("""
                        INSERT INTO system_config (config_key, config_value, description)
                        VALUES (?, ?, ?)
                        ON CONFLICT (config_key) DO UPDATE SET
                            config_value = EXCLUDED.config_value,
                            description = EXCLUDED.description,
                            updated_at = CURRENT_TIMESTAMP
                    """),
                    (key, val, desc),
                )
            else:
                cur.execute(
                    convert(
                        "INSERT OR REPLACE INTO system_config (config_key, config_value, description) VALUES (?, ?, ?)"
                    ),
                    (key, val, desc),
                )
        conn.commit()
    finally:
        try:
            conn.close()
        except Exception:
            pass


def ensure_default_config() -> None:
    """首次启动写入默认 Sheet URL（与 standalone config.txt 一致）。"""
    if not _hooks.get("get_db"):
        return
    url, _source, _year = _read_db_config()
    if url:
        return
    def_url, def_year = _config_txt_default()
    _write_db_config(
        _standalone_module().normalize_url(def_url),
        "standalone 默认",
        def_year,
    )


def _ensure_cache_loaded() -> None:
    with _lock:
        if _cache["loaded"]:
            return
        url, source, year = _read_db_config()
        if not url:
            def_url, def_year = _config_txt_default()
            url = _standalone_module().normalize_url(def_url)
            source = source or "standalone 默认"
            year = year if year is not None else def_year
            try:
                _write_db_config(url, source, year)
            except Exception:
                pass
        _cache.update({"backend": url, "source": source or "系统默认", "year": year, "loaded": True})


def get_backend() -> str:
    _ensure_cache_loaded()
    with _lock:
        return _cache["backend"]


def get_backend_source() -> str:
    _ensure_cache_loaded()
    with _lock:
        return _cache["source"]


def get_year_override() -> int | None:
    _ensure_cache_loaded()
    with _lock:
        return _cache["year"]


def get_backend_kind() -> str:
    rd = _standalone_module()
    return "sheet" if rd.is_sheet_url(get_backend()) else "api"


def set_backend(url: str, source: str = "用户设置", year: int | None = None) -> None:
    rd = _standalone_module()
    url = rd.normalize_url(url)
    with _lock:
        _cache.update({"backend": url, "source": source, "year": year, "loaded": True})
    _write_db_config(url, source, year)
    rd.invalidate_sheet_cache()


def is_local_inbound_backend(backend: str, request_host: str | None) -> bool:
    if not backend:
        return True
    b = backend.rstrip("/").lower()
    if b in ("__local__", "local", "self"):
        return True
    try:
        p = urlparse(backend)
        host = (p.hostname or "").lower()
    except ValueError:
        return False
    if host in ("127.0.0.1", "localhost", "0.0.0.0"):
        return True
    if request_host:
        rh = request_host.split(":")[0].lower()
        if host == rh:
            return True
    return False


def fetch_records(start_date: str | None, end_date: str | None, request_host: str | None = None) -> list:
    rd = _standalone_module()
    backend = get_backend()
    if rd.is_sheet_url(backend):
        return rd.fetch_sheet_records(
            backend,
            start_date=start_date,
            end_date=end_date,
            year_override=get_year_override(),
        )
    if is_local_inbound_backend(backend, request_host):
        fn = _hooks.get("fetch_local_records")
        if not fn:
            raise RuntimeError("fetch_local_records 未配置")
        return fn(start_date, end_date)

    target = urljoin(backend + "/", "api/outbound/records")
    params = {}
    if start_date:
        params["start_date"] = start_date
    if end_date:
        params["end_date"] = end_date
    r = requests.get(target, params=params, timeout=30)
    r.raise_for_status()
    data = r.json()
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and "error" in data:
        raise RuntimeError(data.get("error") or "远程 API 错误")
    return []


def render_route_distribution_html(file_path: str) -> str:
    rd = _standalone_module()
    with open(file_path, "r", encoding="utf-8") as f:
        h = f.read()
    backend = get_backend()
    kind = "Google Sheet" if rd.is_sheet_url(backend) else "API"
    display = backend if len(backend) <= 60 else backend[:28] + "…" + backend[-28:]
    h = h.replace(
        '<a href="/outbound-stats" class="back-link">← 返回出库统计</a>',
        '<a href="/route-distribution/setup" class="back-link" '
        'title="点击切换数据源（API / Google Sheet）" '
        'style="font-size:12px;color:var(--muted);text-decoration:none;">'
        f'⚙ 数据源 [{kind}]: {display}</a>',
    )
    h = h.replace(
        "基于 <code>/api/outbound/records</code>",
        "基于 <code>/api/route-distribution/outbound/records</code>（standalone 方案：API / Google Sheet）",
    )
    h = h.replace("/api/outbound/records", "/api/route-distribution/outbound/records")
    return h


def probe_backend(url: str, timeout=None):
    rd = _standalone_module()
    if timeout is not None:
        return rd.probe_backend(url, timeout=timeout)
    return rd.probe_backend(url)


def lan_scan(ports=None):
    rd = _standalone_module()
    port_list = ports if ports is not None else rd.SCAN_PORTS_DEFAULT
    return rd.lan_scan(ports=port_list), [str(n) for n in rd.subnets_for_scan()]


def invalidate_sheet_cache() -> None:
    _standalone_module().invalidate_sheet_cache()


def get_setup_html() -> str:
    html = _standalone_module().SETUP_HTML
    pairs = [
        ('href="/"', 'href="/route-distribution"'),
        ("location.href='/';", "location.href='/route-distribution';"),
        ("/api/current-backend", "/api/route-distribution/current-backend"),
        ("/api/probe", "/api/route-distribution/probe"),
        ("/api/set-backend", "/api/route-distribution/set-backend"),
        ("/api/lan-scan", "/api/route-distribution/lan-scan"),
    ]
    for old, new in pairs:
        html = html.replace(old, new)
    return html
