"""Подготовка базы: таблицы, миграции, новые карточки, роли админов.

Обычный сервер делает это при старте. На Vercel старт функции не гарантирует lifespan,
поэтому подготовка выполняется при первом запросе в экземпляре (ensure_ready)."""
from __future__ import annotations

from .auth import sync_admin_roles
from .cards import seed_cards
from .config import settings
from .db import SessionLocal, init_db

_ready = False


async def setup_database() -> None:
    if settings.serverless and settings.database_url.startswith("sqlite"):
        # на Vercel файловая система только для чтения: локальная SQLite невозможна
        raise RuntimeError("DATABASE_URL is not set: in serverless mode use Postgres (Supabase), not SQLite")
    await init_db()
    async with SessionLocal() as session:
        await seed_cards(session)
        await sync_admin_roles(session)


async def ensure_ready() -> None:
    global _ready
    if _ready or not settings.serverless:
        return
    await setup_database()
    _ready = True
