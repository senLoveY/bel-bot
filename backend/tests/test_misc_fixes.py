"""Регрессионные тесты: гонка при загрузке карточек, utcnow, поля /api/health."""
from datetime import datetime, timedelta, timezone

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.api import create_app
from app.cards import seed_cards
from app.db import SessionLocal, utcnow


async def test_seed_race_with_another_instance_is_harmless():
    """Второй экземпляр Vercel загружает те же карточки одновременно: ошибка уникальности не роняет запрос."""
    async with SessionLocal() as session:
        real_execute = session.execute

        async def execute(stmt, *a, **kw):
            result = await real_execute(stmt, *a, **kw)
            if "cards.slug" in str(stmt) and "FROM cards" in str(stmt):
                return EmptyResult()  # «не видим» карточки, которые уже вставил другой экземпляр
            return result

        session.execute = execute
        assert await seed_cards(session) == 0


class EmptyResult:
    def scalars(self):
        return iter(())


def test_utcnow_is_naive_utc():
    now = utcnow()
    assert now.tzinfo is None
    assert abs(now - datetime.now(timezone.utc).replace(tzinfo=None)) < timedelta(seconds=5)


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=create_app()), base_url="http://t") as c:
        yield c


async def test_health_has_no_debug_leftovers(client):
    body = (await client.get("/api/health")).json()
    assert set(body) == {"serverless", "vercel_env", "database_driver", "env_set"}
