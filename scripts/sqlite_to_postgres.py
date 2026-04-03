#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
将本地 SQLite（默认 inbound.db）全量导入 PostgreSQL，覆盖目标库 public schema 中的数据。

用法:
  set DATABASE_URL=postgresql://...
  python scripts/sqlite_to_postgres.py [path/to/inbound.db]

或:
  python scripts/sqlite_to_postgres.py inbound.db "postgresql://..."

默认（推荐）: 先导入到临时 schema `_sqlite_sync_staging`，校验行数后再在**单事务**内
DROP public 并将 staging 重命名为 public。若导入中途失败，线上 public 数据不会被清空。

若必须恢复旧行为（先删 public 再导，易中途丢数），可设环境变量:
  SQLITE_SYNC_DIRECT_PUBLIC=1
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text

from neon_database_url import effective_database_url

STAGING_SCHEMA = "_sqlite_sync_staging"
ROOT = Path(__file__).resolve().parent.parent


def _load_env() -> None:
    """Load .env then neon_sync.env（与 nightly_neon_sync 一致）。"""
    incoming = (os.environ.get("DATABASE_URL") or "").strip()
    try:
        from dotenv import load_dotenv

        load_dotenv(ROOT / ".env")
        load_dotenv(ROOT / "neon_sync.env", override=True)
    except ImportError:
        _load_env_fallback_plain()
    if incoming:
        os.environ["DATABASE_URL"] = incoming


def _load_env_fallback_plain() -> None:
    if not (ROOT / "neon_sync.env").is_file():
        return
    try:
        for line in (ROOT / "neon_sync.env").read_text(encoding="utf-8").splitlines():
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
    """部分 psycopg2 对 channel_binding 支持不完整，必要时去掉该参数。"""
    uri = uri.strip()
    if not uri:
        return uri
    uri = re.sub(r"([&?])channel_binding=[^&]*", "", uri)
    uri = uri.replace("?&", "?").rstrip("?&")
    return uri


def _log_pg_verify(pg_engine, pg_uri: str) -> None:
    """Print target host/db and public table count so Neon UI can be matched to this connection."""
    try:
        from sqlalchemy.engine import make_url

        u = make_url(pg_uri)
        print(
            f"PostgreSQL 目标: host={u.host} database={u.database} user={u.username}",
            flush=True,
        )
    except Exception:
        print("PostgreSQL 目标: (URI 解析失败)", flush=True)
    try:
        with pg_engine.connect() as conn:
            db = conn.execute(text("SELECT current_database()")).scalar()
            print(f"PostgreSQL current_database: {db}", flush=True)
            n = conn.execute(
                text(
                    "SELECT count(*) FROM information_schema.tables "
                    "WHERE table_schema = 'public' AND table_type = 'BASE TABLE'"
                )
            ).scalar()
            rows = conn.execute(
                text(
                    "SELECT tablename FROM pg_tables WHERE schemaname = 'public' "
                    "ORDER BY tablename LIMIT 8"
                )
            ).fetchall()
            sample = ", ".join(str(r[0]) for r in rows) if rows else "(none)"
            print(
                f"PostgreSQL public: {int(n)} 张用户表；示例表名: {sample}",
                flush=True,
            )
            print(
                "Neon 提示: 控制台「Tables」需选对分支。请在 Branches 里找到"
                "「Connection string」里含本机 host 的分支，再打开 Tables / SQL Editor。",
                flush=True,
            )
    except Exception as e:
        print(f"WARNING: 无法统计 public 表: {e}", flush=True)


def sqlite_primary_key_columns(sqlite_path: str, table: str) -> list[str] | None:
    """Return ordered PK column names from SQLite PRAGMA, or None if no PK."""
    import sqlite3

    conn = sqlite3.connect(sqlite_path)
    try:
        rows = conn.execute(f'PRAGMA table_info("{table}")').fetchall()
        parts = [(r[5], r[1]) for r in rows if r[5] and int(r[5]) > 0]
        if not parts:
            return None
        parts.sort(key=lambda x: x[0])
        return [name for _, name in parts]
    finally:
        conn.close()


def apply_primary_keys(
    sqlite_path: str, pg_engine, tables: list[str], schema: str | None = None
) -> None:
    """Restore PRIMARY KEYs from SQLite metadata (pandas to_sql does not create them)."""
    prefix = f'"{schema}".' if schema else ""
    for t in tables:
        cols = sqlite_primary_key_columns(sqlite_path, t)
        if not cols:
            continue
        quoted = ", ".join(f'"{c}"' for c in cols)
        ddl = f"ALTER TABLE {prefix}\"{t}\" ADD PRIMARY KEY ({quoted})"
        try:
            with pg_engine.connect() as conn:
                conn.execute(text(ddl))
                conn.commit()
            print(f"  PK -> {t} ({cols})", flush=True)
        except Exception as e:
            print(f"  PK skip {t}: {e}", flush=True)


def list_sqlite_tables(sqlite_path: str) -> list[str]:
    import sqlite3

    conn = sqlite3.connect(sqlite_path)
    try:
        rows = conn.execute(
            """
            SELECT name FROM sqlite_master
            WHERE type='table' AND name NOT LIKE 'sqlite_%'
            ORDER BY name
            """
        ).fetchall()
        return [r[0] for r in rows]
    finally:
        conn.close()


def sqlite_row_count(sqlite_path: str, table: str) -> int:
    import sqlite3

    conn = sqlite3.connect(sqlite_path)
    try:
        return int(conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])
    finally:
        conn.close()


def verify_row_counts(
    sqlite_path: str, pg_engine, tables: list[str], pg_schema: str | None
) -> bool:
    """Return True if every table's row count matches between SQLite and PostgreSQL."""
    ok = True
    prefix = f'"{pg_schema}".' if pg_schema else ""
    for t in tables:
        s = sqlite_row_count(sqlite_path, t)
        with pg_engine.connect() as conn:
            r = conn.execute(text(f"SELECT COUNT(*) FROM {prefix}\"{t}\"")).scalar()
        r = int(r or 0)
        if s != r:
            print(
                f"ERROR: 行数不一致 {t}: SQLite={s} PostgreSQL={r}",
                file=sys.stderr,
            )
            ok = False
    return ok


def _sqlite_outbound_agg(sqlite_path: str) -> dict[tuple[str, str, str], tuple[int, float]]:
    import sqlite3

    conn = sqlite3.connect(sqlite_path)
    try:
        rows = conn.execute(
            """
            SELECT
              CAST(record_date AS TEXT) AS record_date,
              COALESCE(route_type, '') AS route_type,
              COALESCE(route_code, '') AS route_code,
              COALESCE(SUM(COALESCE(vehicle_count, 1)), 0) AS vehicles,
              COALESCE(SUM(COALESCE(cost, 0)), 0) AS total_cost
            FROM outbound_records
            GROUP BY CAST(record_date AS TEXT), COALESCE(route_type, ''), COALESCE(route_code, '')
            """
        ).fetchall()
        out: dict[tuple[str, str, str], tuple[int, float]] = {}
        for d, t, c, v, s in rows:
            out[(str(d), str(t), str(c))] = (int(v or 0), round(float(s or 0), 4))
        return out
    finally:
        conn.close()


def _pg_outbound_agg(pg_engine, pg_schema: str) -> dict[tuple[str, str, str], tuple[int, float]]:
    q = text(
        f"""
        SELECT
          CAST(record_date AS TEXT) AS record_date,
          COALESCE(route_type, '') AS route_type,
          COALESCE(route_code, '') AS route_code,
          COALESCE(SUM(COALESCE(vehicle_count, 1)), 0) AS vehicles,
          COALESCE(SUM(COALESCE(cost, 0)), 0) AS total_cost
        FROM "{pg_schema}"."outbound_records"
        GROUP BY CAST(record_date AS TEXT), COALESCE(route_type, ''), COALESCE(route_code, '')
        """
    )
    with pg_engine.connect() as conn:
        rows = conn.execute(q).fetchall()
    out: dict[tuple[str, str, str], tuple[int, float]] = {}
    for d, t, c, v, s in rows:
        out[(str(d), str(t), str(c))] = (int(v or 0), round(float(s or 0), 4))
    return out


def verify_outbound_aggregates(sqlite_path: str, pg_engine, pg_schema: str | None) -> bool:
    """Critical consistency guard: compare outbound_records aggregates key-by-key."""
    if not pg_schema:
        return True
    try:
        s_map = _sqlite_outbound_agg(sqlite_path)
        p_map = _pg_outbound_agg(pg_engine, pg_schema)
    except Exception as e:
        print(f"ERROR: 出库聚合校验执行失败: {e}", file=sys.stderr)
        return False

    ok = True
    all_keys = sorted(set(s_map.keys()) | set(p_map.keys()))
    bad: list[tuple[tuple[str, str, str], tuple[int, float], tuple[int, float]]] = []
    for k in all_keys:
        sv = s_map.get(k, (0, 0.0))
        pv = p_map.get(k, (0, 0.0))
        if sv != pv:
            ok = False
            bad.append((k, sv, pv))
            if len(bad) >= 20:
                break

    if not ok:
        print(
            "ERROR: outbound_records 聚合不一致（按 record_date+route_type+route_code）。",
            file=sys.stderr,
        )
        for (d, t, c), sv, pv in bad:
            print(
                f"  mismatch {d} {t} {c}: SQLite vehicles/cost={sv} PostgreSQL vehicles/cost={pv}",
                file=sys.stderr,
            )
    else:
        lav_sqlite = sum(v[0] for k, v in s_map.items() if k[2] == "LAV")
        lav_pg = sum(v[0] for k, v in p_map.items() if k[2] == "LAV")
        print(
            f"outbound_records 聚合校验通过（keys={len(s_map)}）。LAV vehicles: SQLite={lav_sqlite} PostgreSQL={lav_pg}",
            flush=True,
        )
    return ok


def direct_public_mode() -> bool:
    v = os.environ.get("SQLITE_SYNC_DIRECT_PUBLIC", "").strip().lower()
    return v in ("1", "true", "yes")


def main() -> int:
    sqlite_path = sys.argv[1] if len(sys.argv) > 1 else str(ROOT / "inbound.db")
    pg_uri = effective_database_url() or (sys.argv[2] if len(sys.argv) > 2 else "")
    if not pg_uri:
        print(
            "ERROR: 请在 neon_sync.env 中设置 DATABASE_URL，或仅设置 DATABASE_URL_PRODUCTION（主库），"
            "或在命令行第二个参数传入 postgresql://...",
            file=sys.stderr,
        )
        return 2

    sqlite_path = str(Path(sqlite_path).resolve())
    if not os.path.isfile(sqlite_path):
        print(f"ERROR: SQLite file not found: {sqlite_path}", file=sys.stderr)
        return 2

    pg_uri = clean_pg_uri(pg_uri)
    if not pg_uri.startswith("postgres"):
        print("ERROR: DATABASE_URL must start with postgresql:// or postgres://", file=sys.stderr)
        return 2

    sqlite_engine = create_engine(f"sqlite:///{sqlite_path}")
    pg_engine = create_engine(pg_uri, pool_pre_ping=True)

    tables = list_sqlite_tables(sqlite_path)
    print(f"SQLite: {sqlite_path} ({len(tables)} tables)")

    use_staging = not direct_public_mode()
    target_schema = None if not use_staging else STAGING_SCHEMA

    if use_staging:
        with pg_engine.connect() as conn:
            conn.execute(text(f'DROP SCHEMA IF EXISTS "{STAGING_SCHEMA}" CASCADE'))
            conn.execute(text(f'CREATE SCHEMA "{STAGING_SCHEMA}"'))
            conn.commit()
        print(
            f"PostgreSQL: 已准备临时 schema `{STAGING_SCHEMA}`（未改动 public，可安全导入）。"
        )
    else:
        with pg_engine.connect() as conn:
            conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
            conn.execute(text("CREATE SCHEMA public"))
            conn.execute(text("GRANT ALL ON SCHEMA public TO public"))
            conn.commit()
        print(
            "PostgreSQL: public schema 已重建（旧数据已删除）。[SQLITE_SYNC_DIRECT_PUBLIC]",
            file=sys.stderr,
        )

    for name in tables:
        print(f"  -> {name} ...", flush=True)
        df = pd.read_sql_query(f'SELECT * FROM "{name}"', sqlite_engine)
        kw: dict = {
            "name": name,
            "con": pg_engine,
            "if_exists": "replace",
            "index": False,
        }
        if target_schema:
            kw["schema"] = target_schema
        if df.empty:
            df.to_sql(**kw)
            continue
        kw["method"] = "multi"
        kw["chunksize"] = 500
        df.to_sql(**kw)

    print("Applying PRIMARY KEYs from SQLite metadata ...")
    apply_primary_keys(sqlite_path, pg_engine, tables, schema=target_schema)

    if use_staging:
        if not verify_row_counts(sqlite_path, pg_engine, tables, STAGING_SCHEMA):
            print(
                "ERROR: 行数校验失败，已放弃切换 public；线上 public 未修改。"
                f" 可手动删除 schema `{STAGING_SCHEMA}` 后重试。",
                file=sys.stderr,
            )
            return 3
        if "outbound_records" in tables and not verify_outbound_aggregates(
            sqlite_path, pg_engine, STAGING_SCHEMA
        ):
            print(
                "ERROR: 出库聚合校验失败，已放弃切换 public；线上 public 未修改。",
                file=sys.stderr,
            )
            return 3
        print("PostgreSQL: 行数校验通过，正在将 staging 切换为 public（单事务）…")
        try:
            with pg_engine.begin() as conn:
                conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
                conn.execute(
                    text(f'ALTER SCHEMA "{STAGING_SCHEMA}" RENAME TO public')
                )
                conn.execute(text("GRANT ALL ON SCHEMA public TO public"))
        except Exception as e:
            print(
                f"ERROR: 切换 public 失败（事务已回滚，原 public 应仍完整）: {e}",
                file=sys.stderr,
            )
            return 4

    _log_pg_verify(pg_engine, pg_uri)
    print("Done: all tables copied to PostgreSQL.")
    return 0


if __name__ == "__main__":
    _load_env()
    raise SystemExit(main())
