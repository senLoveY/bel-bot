from __future__ import annotations

import os
from datetime import datetime

from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from .config import settings


class Base(DeclarativeBase):
    pass


engine = create_async_engine(settings.database_url)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


def utcnow() -> datetime:
    """Наивное UTC-время: так одинаково хранится и в SQLite, и в Postgres."""
    return datetime.utcnow()


async def init_db() -> None:
    if settings.database_url.startswith("sqlite"):
        path = settings.database_url.split("///", 1)[-1]
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    from . import models  # noqa: F401  (регистрирует таблицы)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await add_missing_columns(conn)


# create_all не добавляет колонки в уже существующие таблицы, поэтому докидываем их вручную
MIGRATIONS = [
    ("users", "explain_lang", "VARCHAR(2) NOT NULL DEFAULT 'ru'"),
    ("users", "streak", "INTEGER NOT NULL DEFAULT 0"),
    ("users", "longest_streak", "INTEGER NOT NULL DEFAULT 0"),
    ("users", "last_seen_day", "VARCHAR(10)"),
    ("cards", "summary_be", "VARCHAR(512)"),
    ("cards", "body_be", "TEXT"),
]


async def add_missing_columns(conn) -> None:
    for table, column, ddl in MIGRATIONS:
        columns = await conn.run_sync(lambda c, t=table: {col["name"] for col in inspect(c).get_columns(t)})
        if column not in columns:
            await conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))


async def get_session():
    async with SessionLocal() as session:
        yield session


__all__ = ["Base", "SessionLocal", "engine", "init_db", "get_session", "utcnow", "AsyncSession"]
