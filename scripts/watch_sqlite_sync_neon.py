#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
本地 SQLite 文件变更后，经防抖延迟自动全量同步到 Neon（PostgreSQL）。

原理：监听数据库文件所在目录，对 inbound.db / -wal / -shm / -journal 等变更触发计时；
在 NEON_SYNC_DEBOUNCE_SECONDS 秒内无新变更后，调用 scripts/sqlite_to_postgres.py。

前置条件：
  - 配置 DATABASE_URL（目标 Neon 连接串），见 neon_sync.env 或 .env
  - pip install -r requirements-neon-sync.txt  （含 watchdog）

用法（项目根目录）:
  set DATABASE_URL=postgresql://...
  python scripts/watch_sqlite_sync_neon.py

可选环境变量:
  DATABASE_PATH   本地 SQLite 路径（默认 项目根/inbound.db）
  NEON_SYNC_DEBOUNCE_SECONDS  防抖秒数（默认 90）
  NEON_SYNC_ENABLED  设为 0 可禁用（便于 CI 中 import 不启动）

注意：全量同步会 DROP SCHEMA public CASCADE，仅适用于「本地为主、Neon 为镜像」的场景。
"""
from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Optional

from neon_database_url import effective_database_url
from neon_subprocess_env import child_python_env

ROOT = Path(__file__).resolve().parent.parent


def _load_env() -> None:
    try:
        from dotenv import load_dotenv

        load_dotenv(ROOT / ".env")
        load_dotenv(ROOT / "neon_sync.env", override=True)
    except ImportError:
        _load_env_plain(ROOT / ".env")
        _load_env_plain(ROOT / "neon_sync.env")


def _load_env_plain(path: Path) -> None:
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
        format="%(asctime)s [%(levelname)s] [watch] %(message)s",
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


def _sqlite_paths() -> Path:
    raw = (os.environ.get("DATABASE_PATH") or "").strip()
    if raw:
        return Path(raw).resolve()
    return (ROOT / "inbound.db").resolve()


def _is_db_related_file(sqlite_file: Path, event_path: str) -> bool:
    name = Path(event_path).name
    base = sqlite_file.name
    # -shm 事件非常频繁且噪声大；仅以主库与 WAL/JOURNAL 触发同步
    allowed = {base, f"{base}-wal", f"{base}-journal", f"{base}.journal"}
    return name in allowed


class DebouncedSync:
    def __init__(self, debounce_sec: float, min_interval_sec: float, run_sync_fn):
        self.debounce_sec = debounce_sec
        self.min_interval_sec = min_interval_sec
        self.run_sync_fn = run_sync_fn
        self._timer: Optional[threading.Timer] = None
        self._lock = threading.Lock()
        self._running = False
        self._pending = False
        self._last_started_at = 0.0

    def notify_change(self) -> None:
        with self._lock:
            if self._running:
                self._pending = True
                return
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None
            self._timer = threading.Timer(self.debounce_sec, self._execute)
            self._timer.daemon = True
            self._timer.start()
            logging.debug("Debounce timer started (%s s)", self.debounce_sec)

    def _execute(self) -> None:
        with self._lock:
            self._timer = None
            if self._running:
                self._pending = True
                return
            now = time.monotonic()
            since_last = now - self._last_started_at
            if since_last < self.min_interval_sec:
                wait = self.min_interval_sec - since_last
                self._timer = threading.Timer(wait, self._execute)
                self._timer.daemon = True
                self._timer.start()
                return
            self._running = True
            self._last_started_at = now
        try:
            self.run_sync_fn()
        finally:
            with self._lock:
                self._running = False
                retry = self._pending
                self._pending = False
            if retry:
                # 运行期间若有变化，重新走完整防抖窗口，避免高频连环全量同步
                self.notify_change()


def _run_sqlite_to_postgres(sqlite_path: Path) -> None:
    url = effective_database_url()
    if not url:
        logging.error("DATABASE_URL / DATABASE_URL_PRODUCTION 未设置; cannot sync.")
        return
    script = ROOT / "scripts" / "sqlite_to_postgres.py"
    if not script.is_file():
        logging.error("Missing %s", script)
        return
    logging.info("Starting SQLite -> Neon sync (%s)", sqlite_path)
    env = child_python_env()
    env["DATABASE_URL"] = url
    proc = subprocess.run(
        [sys.executable, str(script), str(sqlite_path)],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if proc.returncode == 0:
        logging.info("Sync finished OK.")
    else:
        logging.error("Sync failed (exit %s)", proc.returncode)
        out = (proc.stdout or "").strip().splitlines()[-8:]
        err = (proc.stderr or "").strip().splitlines()[-8:]
        for line in out:
            logging.error("[sync stdout] %s", line)
        for line in err:
            logging.error("[sync stderr] %s", line)


def main() -> int:
    _load_env()
    _setup_logging()

    if os.environ.get("NEON_SYNC_ENABLED", "1").strip() == "0":
        logging.info("NEON_SYNC_ENABLED=0, exit.")
        return 0

    try:
        from watchdog.events import FileSystemEventHandler
        from watchdog.observers import Observer
    except ImportError:
        logging.error("Please install: pip install watchdog  (or pip install -r requirements-neon-sync.txt)")
        return 2

    sqlite_path = _sqlite_paths()
    if not sqlite_path.is_file():
        logging.error("SQLite file not found: %s", sqlite_path)
        return 2

    debounce = float(os.environ.get("NEON_SYNC_DEBOUNCE_SECONDS", "90"))
    min_interval = float(os.environ.get("NEON_SYNC_MIN_INTERVAL_SECONDS", "30"))
    watch_dir = str(sqlite_path.parent)

    debouncer = DebouncedSync(
        debounce_sec=debounce,
        min_interval_sec=min_interval,
        run_sync_fn=lambda: _run_sqlite_to_postgres(sqlite_path),
    )

    class Handler(FileSystemEventHandler):
        def __init__(self):
            self._last_event_key = None
            self._last_event_ts = 0.0

        def on_any_event(self, event):  # noqa: N802
            if event.is_directory:
                return
            if not _is_db_related_file(sqlite_path, event.src_path):
                return
            # watchdog 在 Windows 上可能对同一事件短时间回调多次，做 1s 去重
            now = time.monotonic()
            key = (event.src_path, getattr(event, "event_type", ""))
            if self._last_event_key == key and (now - self._last_event_ts) < 1.0:
                return
            self._last_event_key = key
            self._last_event_ts = now
            logging.info("Detected change: %s (%s)", event.src_path, getattr(event, "event_type", ""))
            debouncer.notify_change()

    logging.info("Watching directory: %s", watch_dir)
    logging.info("SQLite file: %s", sqlite_path)
    logging.info("Debounce: %s s after last change", debounce)
    logging.info("Min sync interval: %s s", min_interval)
    logging.info(
        "Target URL: %s",
        "set" if effective_database_url() else "MISSING",
    )

    observer = Observer()
    observer.schedule(Handler(), watch_dir, recursive=False)
    observer.start()
    try:
        import time

        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logging.info("Stopping observer...")
        observer.stop()
    observer.join()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as e:
        logging.basicConfig(level=logging.INFO)
        logging.exception("watch_sqlite_sync_neon crashed: %s", e)
        raise SystemExit(1)
