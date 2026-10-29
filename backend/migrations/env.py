"""Окружение Alembic.

Адрес и драйвер берутся из настроек приложения (DATABASE_URL, асинхронный драйвер).
Если миграции запускает само приложение (app.migrations), соединение уже передано
в config.attributes["connection"] и новое не открывается."""
import asyncio

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

from app import models  # noqa: F401  (регистрирует таблицы в metadata)
from app.config import settings
from app.db import Base, engine_kwargs

target_metadata = Base.metadata


def do_run_migrations(connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=connection.dialect.name == "sqlite",  # SQLite не умеет ALTER COLUMN
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_with_own_engine() -> None:
    engine = create_async_engine(settings.database_url, **engine_kwargs(settings.database_url, serverless=True))
    async with engine.begin() as conn:
        await conn.run_sync(do_run_migrations)
    await engine.dispose()


connection = context.config.attributes.get("connection")
if connection is not None:
    do_run_migrations(connection)
else:
    asyncio.run(run_with_own_engine())
