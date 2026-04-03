"""Resolve which Neon URL single-target sync scripts should use."""
from __future__ import annotations

import os


def effective_database_url() -> str:
    """DATABASE_URL if set; else DATABASE_URL_PRODUCTION (multi-target config)."""
    u = (os.environ.get("DATABASE_URL") or "").strip()
    if u:
        return u
    return (os.environ.get("DATABASE_URL_PRODUCTION") or "").strip()
