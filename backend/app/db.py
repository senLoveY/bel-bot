from __future__ import annotations

import os
import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from .config import settings


class Base(DeclarativeBase):
    pass


def engine_kwargs(database_url: str, serverless: bool) -> dict:
    kwargs: dict = {}
    if serverless:
        # каждый вызов функции живёт недолго: своё соединение без пула внутри приложения
        kwargs["poolclass"] = NullPool
    if database_url.startswith("postgresql+asyncpg"):
        # пулер Supabase (pgbouncer) не поддерживает кэш подготовленных запросов asyncpg
        kwargs["connect_args"] = {
            "statement_cache_size": 0,
            "prepared_statement_name_func": lambda: f"__asyncpg_{uuid.uuid4()}__",
        }
    return kwargs


engine = create_async_engine(settings.database_url, **engine_kwargs(settings.database_url, settings.serverless))
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


def utcnow() -> datetime:
    """Наивное UTC-время: так одинаково хранится и в SQLite, и в Postgres."""
    return datetime.utcnow()


async def init_db() -> None:
    """Приводит схему базы к последней миграции Alembic (см. app/migrations.py)."""
    if settings.database_url.startswith("sqlite"):
        path = settings.database_url.split("///", 1)[-1]
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    from . import models  # noqa: F401  (регистрирует таблицы)
    from .migrations import upgrade_database

    await upgrade_database(engine)


async def get_session():
    async with SessionLocal() as session:
        yield session


__all__ = ["Base", "SessionLocal", "engine", "init_db", "get_session", "utcnow", "AsyncSession"]
