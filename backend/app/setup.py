"""Подготовка базы: таблицы, миграции, новые карточки, роли админов.

Обычный сервер делает это при старте. На Vercel старт функции не гарантирует lifespan,
поэтому подготовка выполняется при первом запросе в экземпляре (ensure_ready)."""
from __future__ import annotations

import logging

from fastapi import HTTPException, Request

from .auth import sync_admin_roles
from .cards import seed_cards
from .config import settings
from .db import SessionLocal, init_db

log = logging.getLogger(__name__)
_ready = False


async def setup_database() -> None:
    if settings.serverless and settings.database_url.startswith("sqlite"):
        # на Vercel файловая система только для чтения: локальная SQLite невозможна
        raise RuntimeError("DATABASE_URL is not set: in serverless mode use Postgres (Supabase), not SQLite")
    await init_db()
    async with SessionLocal() as session:
        await seed_cards(session)
        await sync_admin_roles(session)


async def ensure_ready(request: Request) -> None:
    global _ready
    if _ready or not settings.serverless or request.url.path == "/api/health":
        return
    try:
        await setup_database()
    except Exception as exc:
        # полный traceback — в логи Vercel; наружу только тип ошибки, без строки подключения и секретов
        log.exception("database setup failed")
        raise HTTPException(503, f"database setup failed: {type(exc).__name__}") from exc
    _ready = True
