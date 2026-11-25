"""Thin database access layer.

Everything reads from a *view*, never from a raw table: the business logic lives
in sql/04_staging_views.sql so SQL and Python cannot drift apart.
"""
from __future__ import annotations

import pandas as pd

from src import config
from src.utils import LOG

_engine = None


def get_engine():
    global _engine
    if _engine is None:
        from sqlalchemy import create_engine
        _engine = create_engine(config.db_url(), pool_pre_ping=True, future=True)
    return _engine


def read_view(view: str, columns: str = "*") -> pd.DataFrame:
    LOG.info("reading %s from MySQL", view)
    return pd.read_sql(f"SELECT {columns} FROM {view}", get_engine())


def read_sql(query: str, params: dict | None = None) -> pd.DataFrame:
    return pd.read_sql(query, get_engine(), params=params or {})


def run_script(path) -> None:
    """Execute a .sql file statement by statement.

    Deliberately simple: no DELIMITER handling, because none of our scripts use
    stored procedures. LOAD DATA ... PREPARE blocks are skipped -- those are run
    from MySQL Workbench via sql/02_load_data.sql.
    """
    from sqlalchemy import text
    sql_text = open(path, encoding="utf-8").read()
    statements = split_sql(sql_text)
    with get_engine().begin() as conn:
        for stmt in statements:
            conn.execute(text(stmt))
    LOG.info("executed %s (%d statements)", path, len(statements))


def split_sql(sql_text: str) -> list[str]:
    """Split on semicolons, ignoring comments and quoted strings."""
    out, buf, quote = [], [], None
    i = 0
    while i < len(sql_text):
        ch = sql_text[i]
        if quote:
            buf.append(ch)
            if ch == quote:
                quote = None
        elif ch in ("'", '"'):
            quote = ch
            buf.append(ch)
        elif ch == "-" and sql_text[i:i + 2] == "--":
            while i < len(sql_text) and sql_text[i] != "\n":
                i += 1
            continue
        elif ch == ";":
            stmt = "".join(buf).strip()
            if stmt:
                out.append(stmt)
            buf = []
        else:
            buf.append(ch)
        i += 1
    tail = "".join(buf).strip()
    if tail:
        out.append(tail)
    return out
