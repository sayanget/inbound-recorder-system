"""飞书开放平台 tenant_access_token（与运单 sheet / CNO 小组分时元数据同步共用）。"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Tuple

import requests

FEISHU_APP_ID = os.getenv("FEISHU_APP_ID", "cli_a9fc1c1c0bb8dbcb").strip()
FEISHU_APP_SECRET = os.getenv("FEISHU_APP_SECRET", "XeStEZgDlQQUnUU93w1d3emYSdMSfiq6").strip()

_TOKEN_URL = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal/"


def feishu_tenant_access_token(
    app_id: Optional[str] = None, app_secret: Optional[str] = None
) -> str:
    aid = (app_id or FEISHU_APP_ID).strip()
    sec = (app_secret or FEISHU_APP_SECRET).strip()
    if not aid or not sec:
        raise RuntimeError("飞书 FEISHU_APP_ID / FEISHU_APP_SECRET 未配置")
    r = requests.post(
        _TOKEN_URL,
        json={"app_id": aid, "app_secret": sec},
        timeout=30,
    )
    if r.status_code != 200:
        raise RuntimeError(f"获取飞书 Token 失败: {r.text}")
    j = r.json()
    if j.get("code") not in (0, None):
        raise RuntimeError(f"获取飞书 Token 失败: {j}")
    token = j.get("tenant_access_token")
    if not token:
        raise RuntimeError("飞书 tenant_access_token 为空")
    return token


def feishu_wiki_get_node(
    tenant_token: str, wiki_token: str
) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[str]]:
    """GET wiki/v2/spaces/get_node → (space_id, node_token, obj_token, obj_type)。"""
    res = requests.get(
        "https://open.feishu.cn/open-apis/wiki/v2/spaces/get_node",
        headers={"Authorization": f"Bearer {tenant_token}"},
        params={"token": wiki_token},
        timeout=30,
    )
    if res.status_code != 200:
        raise RuntimeError(f"获取 Wiki 节点失败: {res.text}")
    j = res.json()
    if j.get("code") not in (0, None):
        raise RuntimeError(f"获取 Wiki 节点失败: {j}")
    data = j.get("data") or {}
    node = data.get("node") if isinstance(data.get("node"), dict) else data
    return (
        node.get("space_id"),
        node.get("node_token"),
        node.get("obj_token"),
        node.get("obj_type"),
    )


def feishu_sheet_col_letter(col_index: int) -> str:
    """0-based column index → A, B, …, Z, AA, …"""
    n = col_index + 1
    s = ""
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def feishu_sheet_read_values(
    tenant_token: str,
    spreadsheet_token: str,
    range_a1: str,
) -> List[List[Any]]:
    """读取指定 range（含 sheetId!A1:Z10）。"""
    url = (
        f"https://open.feishu.cn/open-apis/sheets/v2/spreadsheets/"
        f"{spreadsheet_token}/values/{range_a1}"
    )
    res = requests.get(
        url,
        headers={"Authorization": f"Bearer {tenant_token}"},
        params={"valueRenderOption": "ToString"},
        timeout=60,
    )
    if res.status_code != 200:
        raise RuntimeError(f"读取表格失败: {res.text}")
    j = res.json()
    if j.get("code") not in (0, None):
        raise RuntimeError(f"读取表格失败: {j}")
    vr = (j.get("data") or {}).get("valueRange") or {}
    return vr.get("values") or []


def feishu_sheet_metainfo(tenant_token: str, spreadsheet_token: str) -> Dict[str, Any]:
    url = (
        f"https://open.feishu.cn/open-apis/sheets/v2/spreadsheets/"
        f"{spreadsheet_token}/metainfo"
    )
    res = requests.get(
        url,
        headers={"Authorization": f"Bearer {tenant_token}"},
        timeout=30,
    )
    if res.status_code != 200:
        raise RuntimeError(f"获取表格 metainfo 失败: {res.text}")
    j = res.json()
    if j.get("code") not in (0, None):
        raise RuntimeError(f"获取表格 metainfo 失败: {j}")
    return j.get("data") or {}


def feishu_sheet_resolve_sheet_id(
    tenant_token: str,
    spreadsheet_token: str,
    *,
    sheet_id: str = "",
    sheet_title: str = "元数据",
) -> str:
    sid = (sheet_id or "").strip()
    if sid:
        return sid
    data = feishu_sheet_metainfo(tenant_token, spreadsheet_token)
    sheets = data.get("sheets") or []
    title = (sheet_title or "").strip()
    if title:
        for sh in sheets:
            if str(sh.get("title") or "").strip() == title:
                return str(sh.get("sheetId") or sh.get("sheet_id") or "").strip()
    if sheets:
        sh0 = sheets[0]
        return str(sh0.get("sheetId") or sh0.get("sheet_id") or "").strip()
    raise RuntimeError("表格中未找到任何工作表")


def feishu_sheet_write_values(
    tenant_token: str,
    spreadsheet_token: str,
    sheet_id: str,
    values: List[List[Any]],
    *,
    start_row: int = 1,
    start_col: int = 1,
) -> Dict[str, Any]:
    """覆盖写入二维数组（从 start_row/start_col 起，1-based）。"""
    if not values:
        raise ValueError("values 为空")
    nrows = len(values)
    ncols = max(len(r) for r in values)
    padded = []
    for row in values:
        r = list(row)
        if len(r) < ncols:
            r.extend([""] * (ncols - len(r)))
        padded.append(r)
    end_col = feishu_sheet_col_letter(start_col - 1 + ncols - 1)
    end_row = start_row + nrows - 1
    start_col_letter = feishu_sheet_col_letter(start_col - 1)
    range_str = f"{sheet_id}!{start_col_letter}{start_row}:{end_col}{end_row}"
    url = (
        f"https://open.feishu.cn/open-apis/sheets/v2/spreadsheets/"
        f"{spreadsheet_token}/values"
    )
    body = {"valueRange": {"range": range_str, "values": padded}}
    res = requests.put(
        url,
        headers={
            "Authorization": f"Bearer {tenant_token}",
            "Content-Type": "application/json",
        },
        json=body,
        timeout=120,
    )
    if res.status_code != 200:
        raise RuntimeError(f"写入表格失败: {res.text}")
    j = res.json()
    if j.get("code") not in (0, None):
        raise RuntimeError(f"写入表格失败: {j}")
    return j.get("data") or {}
