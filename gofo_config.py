# Copyright (c) 2026 Fan Yang. All rights reserved.
# 商业/营利性使用须事先书面许可；未经授权构成侵权，权利人保留依法主张全部救济之权利。
import os
from typing import Optional


def get_gofo_token(default_token: Optional[str] = None) -> str:
    """
    Resolve Gofo API token from:
    1) GOFO_TOKEN env var (explicit override)
    2) database system_config table (config_key='gofo_admin_token')  ← UI updates here
    3) gofo_token.txt in project root (or GOFO_TOKEN_FILE env var)  ← legacy fallback
    4) fallback to default_token

    DB is checked before the file because the admin UI (/api/gofo/dms/login-and-save)
    persists fresh tokens to `system_config`. If an older `gofo_token.txt` is still
    on disk, we must not let it shadow the newly-saved DB token.
    """
    # 1) Env Var
    token = os.environ.get("GOFO_TOKEN", "").strip()
    if token:
        if token.lower().startswith("bearer "):
            token = token[7:].strip()
        return token

    # 2) Database lookup (UI writes here; highest-priority persisted source)
    try:
        import sqlite3
        # Resolve DB path conservatively
        db_path = os.environ.get('DATABASE_PATH')
        if not db_path:
            db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'inbound.db')

        if os.path.exists(db_path):
            conn = sqlite3.connect(db_path, timeout=5)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT config_value FROM system_config WHERE config_key = 'gofo_admin_token'")
            row = cursor.fetchone()
            conn.close()
            if row and row['config_value']:
                db_token = row['config_value'].strip()
                if db_token.lower().startswith("bearer "):
                    db_token = db_token[7:].strip()
                if db_token:
                    return db_token
    except Exception:
        # Silently fail and fall back
        pass

    # 3) File (legacy fallback, e.g. for scripts/gofo_login_token.py)
    token_file = os.environ.get("GOFO_TOKEN_FILE", "").strip()
    if not token_file:
        token_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gofo_token.txt")

    try:
        if os.path.exists(token_file):
            file_token = open(token_file, "r", encoding="utf-8").read().strip()
            if file_token.lower().startswith("bearer "):
                file_token = file_token[7:].strip()
            if file_token:
                return file_token
    except OSError:
        pass

    # 4) Fallback
    if default_token:
        return default_token

    raise RuntimeError(
        "Gofo token not found. Set GOFO_TOKEN env var, update system_config in DB, or create gofo_token.txt."
    )

