from __future__ import annotations

from sqlalchemy import Engine, create_engine


def create_db_engine(database_url: str, *, echo: bool = False) -> Engine:
    return create_engine(database_url, echo=echo, pool_pre_ping=True, future=True)
