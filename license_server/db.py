"""数据库引擎与会话（LICENSE_DATABASE_URL：默认 SQLite）。"""
from __future__ import annotations

import os

# 先于 engine 创建加载项目根 .env（与 single_app 共用配置）
def _load_dotenv_early() -> None:
    try:
        from dotenv import load_dotenv

        _here = os.path.dirname(os.path.abspath(__file__))
        _root = os.path.dirname(_here)
        load_dotenv(os.path.join(_root, ".env"))
    except ImportError:
        pass


_load_dotenv_early()

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from license_server.models import Base

_DEFAULT_SQLITE = "sqlite:///license_server.db"


def database_url() -> str:
    return (os.environ.get("LICENSE_DATABASE_URL") or _DEFAULT_SQLITE).strip()


def make_engine():
    url = database_url()
    # SQLite 多线程（Flask 每请求一线程）需 check_same_thread=False
    kwargs = {}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    return create_engine(url, pool_pre_ping=True, **kwargs)


engine = make_engine()
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, class_=Session)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
