from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import create_async_engine

from app import models  # noqa: F401
from app.db import Base
from app.migrations import upgrade_database

HEAD = "0002"


def make_engine(tmp_path):
    return create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/migrations.db")


async def tables_and_version(engine):
    async with engine.connect() as conn:
        tables = await conn.run_sync(lambda c: set(inspect(c).get_table_names()))
        version = (await conn.execute(text("SELECT version_num FROM alembic_version"))).scalar()
    return tables, version


async def test_fresh_database_is_built_by_migrations(tmp_path):
    engine = make_engine(tmp_path)
    await upgrade_database(engine)
    await upgrade_database(engine)  # повторный запуск ничего не делает
    tables, version = await tables_and_version(engine)
    await engine.dispose()
    assert set(Base.metadata.tables) <= tables
    assert version == HEAD


async def test_migrations_match_models(tmp_path):
    """Если поменяли app/models.py и забыли миграцию — этот тест упадёт."""
    engine = make_engine(tmp_path)
    await upgrade_database(engine)
    async with engine.connect() as conn:
        diff = await conn.run_sync(lambda c: compare_metadata(MigrationContext.configure(c), Base.metadata))
    await engine.dispose()
    assert diff == []


async def test_legacy_database_is_stamped_and_upgraded(tmp_path):
    """База, созданная до Alembic: старый набор колонок у users, новых таблиц нет."""
    engine = make_engine(tmp_path)
    legacy = [t for name, t in Base.metadata.tables.items() if name not in ("users", "events", "used_login_tokens")]
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "CREATE TABLE users (id BIGINT PRIMARY KEY, first_name VARCHAR(128) NOT NULL, username VARCHAR(64),"
                " tz VARCHAR(64) NOT NULL, tz_set BOOLEAN NOT NULL, send_time VARCHAR(5) NOT NULL,"
                " is_active BOOLEAN NOT NULL, created_at DATETIME NOT NULL)"
            )
        )
        await conn.run_sync(lambda c: Base.metadata.create_all(c, tables=legacy))
        await conn.execute(
            text(
                "INSERT INTO users (id, first_name, tz, tz_set, send_time, is_active, created_at)"
                " VALUES (1, 'Ala', 'Europe/Minsk', 0, '09:00', 1, '2026-01-01 00:00:00')"
            )
        )

    await upgrade_database(engine)

    tables, version = await tables_and_version(engine)
    async with engine.connect() as conn:
        row = (await conn.execute(text("SELECT role, streak, explain_lang FROM users WHERE id = 1"))).one()
    await engine.dispose()
    assert {"events", "used_login_tokens"} <= tables
    assert version == HEAD
    assert tuple(row) == ("user", 0, "ru")  # данные сохранены, недостающие колонки добавлены
