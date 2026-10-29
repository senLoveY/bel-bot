"""Применение миграций Alembic из приложения.

Новая база создаётся миграциями с нуля. База, созданная до перехода на Alembic
(create_all + ручное добавление колонок), сначала дополняется недостающими колонками,
помечается базовой ревизией 0001 и уже потом догоняется до последней ревизии."""
from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text

BACKEND_DIR = Path(__file__).resolve().parents[1]
BASELINE = "0001"

# колонки, которые старый код добавлял вручную; нужны, чтобы старая база совпала с ревизией 0001
LEGACY_COLUMNS = [
    ("users", "explain_lang", "VARCHAR(2) NOT NULL DEFAULT 'ru'"),
    ("users", "streak", "INTEGER NOT NULL DEFAULT 0"),
    ("users", "longest_streak", "INTEGER NOT NULL DEFAULT 0"),
    ("users", "last_seen_day", "VARCHAR(10)"),
    ("users", "role", "VARCHAR(16) NOT NULL DEFAULT 'user'"),
    ("cards", "summary_be", "VARCHAR(512)"),
    ("cards", "body_be", "TEXT"),
    ("cards", "published", "BOOLEAN NOT NULL DEFAULT TRUE"),
]


def alembic_config(connection=None) -> Config:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    if connection is not None:
        cfg.attributes["connection"] = connection
    return cfg


def _fill_legacy_columns(sync_conn) -> None:
    inspector = inspect(sync_conn)
    for table, column, ddl in LEGACY_COLUMNS:
        if column not in {c["name"] for c in inspector.get_columns(table)}:
            sync_conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))


def _upgrade(sync_conn) -> None:
    tables = set(inspect(sync_conn).get_table_names())
    cfg = alembic_config(sync_conn)
    if "users" in tables and "alembic_version" not in tables:
        _fill_legacy_columns(sync_conn)
        command.stamp(cfg, BASELINE)
    command.upgrade(cfg, "head")


async def upgrade_database(engine) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(_upgrade)
