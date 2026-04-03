#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sync local SQLite -> Neon: pick production, sandbox, or both (sequential).

Reads from .env / neon_sync.env (same as other sync scripts):
  DATABASE_URL_PRODUCTION  — 主库
  DATABASE_URL_SANDBOX     — 测试库

可选命令行（非交互）:
  --production
  --sandbox
  --all
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_env() -> None:
    try:
        from dotenv import load_dotenv

        load_dotenv(ROOT / ".env")
        load_dotenv(ROOT / "neon_sync.env", override=True)
    except ImportError:
        _load_env_fallback_plain()


def _load_env_fallback_plain() -> None:
    path = ROOT / "neon_sync.env"
    if not path.is_file():
        return
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            k, v = k.strip(), v.strip().strip('"').strip("'")
            if k:
                os.environ[k] = v
    except OSError:
        pass


def clean_pg_uri(uri: str) -> str:
    uri = uri.strip()
    if not uri:
        return uri
    uri = re.sub(r"([&?])channel_binding=[^&]*", "", uri)
    uri = uri.replace("?&", "?").rstrip("?&")
    return uri


def normalize_neon_url(raw: str) -> str:
    raw = raw.strip()
    if raw.lower().startswith("psql "):
        raw = raw[4:].strip()
    if (raw.startswith("'") and raw.endswith("'")) or (raw.startswith('"') and raw.endswith('"')):
        raw = raw[1:-1]
    return clean_pg_uri(raw)


def _run_one(database_url: str, label: str) -> int:
    from neon_subprocess_env import child_python_env

    script = ROOT / "scripts" / "sqlite_to_postgres.py"
    env = child_python_env()
    env["DATABASE_URL"] = database_url
    env.setdefault("PYTHONIOENCODING", "utf-8")
    print(f"\n========== Sync: {label} ==========\n", flush=True)
    r = subprocess.run(
        [sys.executable, str(script)],
        cwd=str(ROOT),
        env=env,
    )
    return int(r.returncode)


def main() -> int:
    _load_env()
    prod = normalize_neon_url(os.environ.get("DATABASE_URL_PRODUCTION") or "")
    sandbox = normalize_neon_url(os.environ.get("DATABASE_URL_SANDBOX") or "")

    ap = argparse.ArgumentParser(description="SQLite -> Neon (production / sandbox / both)")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--production", action="store_true", help="仅同步到 production")
    g.add_argument("--sandbox", action="store_true", help="仅同步到 sandbox")
    g.add_argument("--all", action="store_true", help="先 production 再 sandbox")
    args = ap.parse_args()

    if args.production or args.sandbox or args.all:
        mode = "production" if args.production else "sandbox" if args.sandbox else "all"
    else:
        print("SQLite -> Neon 多目标同步\n")
        print("  1) 主库 production (DATABASE_URL_PRODUCTION)")
        print("  2) 测试库 sandbox (DATABASE_URL_SANDBOX)")
        print("  3) 全面同步（先 production，再 sandbox）")
        print()
        choice = input("请选择 [1/2/3]: ").strip()
        mode = {"1": "production", "2": "sandbox", "3": "all"}.get(choice, "")
        if not mode:
            print("无效选择。", file=sys.stderr)
            return 2

    if mode in ("production", "all"):
        if not prod:
            print(
                "ERROR: 未设置 DATABASE_URL_PRODUCTION（请在 neon_sync.env 中配置）。",
                file=sys.stderr,
            )
            return 2
        if not prod.startswith("postgres"):
            print(
                "ERROR: DATABASE_URL_PRODUCTION 必须是 postgresql:// 或 postgres://",
                file=sys.stderr,
            )
            return 2

    if mode in ("sandbox", "all"):
        if not sandbox:
            print(
                "ERROR: 未设置 DATABASE_URL_SANDBOX（请在 neon_sync.env 中配置）。",
                file=sys.stderr,
            )
            return 2
        if not sandbox.startswith("postgres"):
            print(
                "ERROR: DATABASE_URL_SANDBOX 必须是 postgresql:// 或 postgres://",
                file=sys.stderr,
            )
            return 2

    if mode == "production":
        return _run_one(prod, "production (主库)")
    if mode == "sandbox":
        return _run_one(sandbox, "sandbox (测试库)")
    # all
    c1 = _run_one(prod, "production (主库)")
    if c1 != 0:
        return c1
    c2 = _run_one(sandbox, "sandbox (测试库)")
    return c2


if __name__ == "__main__":
    raise SystemExit(main())
