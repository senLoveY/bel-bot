from __future__ import annotations

import os
from datetime import datetime

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


async def get_session():
    async with SessionLocal() as session:
        yield session


__all__ = ["Base", "SessionLocal", "engine", "init_db", "get_session", "utcnow", "AsyncSession"]
