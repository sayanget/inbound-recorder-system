#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Nightly sync: local SQLite (inbound.db) -> Neon PostgreSQL.

Loads credentials from environment (recommended):
  - DATABASE_URL in .env or neon_sync.env, or DATABASE_URL_PRODUCTION if DATABASE_URL is empty

Does NOT embed secrets in code. Copy neon_sync.env.example to neon_sync.env and set DATABASE_URL.

Intended to be run by Windows Task Scheduler daily at 00:00 (see install_neon_nightly_sync.bat).
"""
from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
import os
import subprocess
import sys
from pathlib import Path

from neon_database_url import effective_database_url
from neon_subprocess_env import child_python_env

ROOT = Path(__file__).resolve().parent.parent


def _load_env() -> None:
    """Load .env then neon_sync.env; latter overrides (fixes empty DATABASE_URL in .env)."""
    try:
        from dotenv import load_dotenv

        load_dotenv(ROOT / ".env")
        # neon_sync.env wins so sync URL can live only here while .env has other keys
        load_dotenv(ROOT / "neon_sync.env", override=True)
    except ImportError:
        _load_env_fallback_plain()


def _load_env_fallback_plain() -> None:
    """If python-dotenv is missing, read KEY=VALUE lines from neon_sync.env only."""
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


def _setup_logging() -> None:
    log_dir = ROOT / "logs"
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / "neon_sync.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            RotatingFileHandler(
                log_file,
                maxBytes=10 * 1024 * 1024,
                backupCount=5,
                encoding="utf-8",
            ),
            logging.StreamHandler(sys.stdout),
        ],
        force=True,
    )


def main() -> int:
    db_url = effective_database_url()
    if not db_url:
        env_file = ROOT / "neon_sync.env"
        dot_env = ROOT / ".env"
        logging.error(
            "未设置同步目标 URL。请在 neon_sync.env 中配置以下之一：\n"
            "  DATABASE_URL=postgresql://...\n"
            "  或 DATABASE_URL_PRODUCTION=postgresql://...（仅配主库时可用此项）\n"
            "推荐（已 gitignore）: %s\n"
            "Also: %s\n"
            "Exists: neon_sync.env=%s  .env=%s",
            env_file,
            dot_env,
            env_file.is_file(),
            dot_env.is_file(),
        )
        return 2

    sqlite_path = ROOT / "inbound.db"
    if not sqlite_path.is_file():
        logging.error("SQLite file not found: %s", sqlite_path)
        return 2

    script = ROOT / "scripts" / "sqlite_to_postgres.py"
    if not script.is_file():
        logging.error("Missing script: %s", script)
        return 2

    logging.info("Neon nightly sync start (SQLite -> PostgreSQL)")
    logging.info("SQLite: %s", sqlite_path)

    env = child_python_env()
    env["DATABASE_URL"] = db_url
    proc = subprocess.run(
        [sys.executable, str(script), str(sqlite_path)],
        cwd=str(ROOT),
        env=env,
    )
    code = proc.returncode
    if code == 0:
        logging.info("Neon nightly sync finished OK (exit %s)", code)
    else:
        logging.error("Neon nightly sync failed (exit %s)", code)
    return code


if __name__ == "__main__":
    _load_env()
    _setup_logging()
    try:
        raise SystemExit(main())
    except Exception as e:
        logging.exception("Neon nightly sync crashed: %s", e)
        raise SystemExit(1)
