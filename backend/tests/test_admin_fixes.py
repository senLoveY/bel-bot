"""Регрессионные тесты админки: длина полей, админы из ADMIN_IDS, число запросов в очереди правок."""
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event, select

from app.api import create_app
from app.config import settings
from app.db import SessionLocal, engine
from app.models import Card, User


def headers(uid: int) -> dict:
    return {"X-Dev-User": str(uid)}


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=create_app()), base_url="http://t") as c:
        yield c


async def make_user(client, uid: int, role: str) -> None:
    await client.get("/api/me", headers=headers(uid))
    async with SessionLocal() as s:
        (await s.get(User, uid)).role = role
        await s.commit()


async def test_too_long_field_is_422_not_500(client):
    """Раньше слишком длинный текст падал в базе (на Postgres — 500)."""
    await make_user(client, 100, "editor")
    r = await client.post(
        "/api/admin/revisions",
        json={"payload": {"kind": "word", "be": "а" * 257, "ru": "x"}},
        headers=headers(100),
    )
    assert r.status_code == 422
    assert r.json()["detail"] == "be is too long: 257 > 256 characters"


async def test_long_text_fields_are_allowed(client):
    await make_user(client, 101, "editor")
    r = await client.post(
        "/api/admin/revisions",
        json={"payload": {"kind": "fact", "be": "Факт", "ru": "x", "body": "т" * 5000}},
        headers=headers(101),
    )
    assert r.status_code == 201  # у body (Text) ограничения длины нет


async def test_admin_from_env_cannot_be_demoted(client, monkeypatch):
    await make_user(client, 102, "admin")
    await make_user(client, 103, "admin")
    monkeypatch.setattr(settings, "admin_ids", "103")
    r = await client.put("/api/admin/users/103/role", json={"role": "user"}, headers=headers(102))
    assert r.status_code == 400 and "ADMIN_IDS" in r.json()["detail"]
    async with SessionLocal() as s:
        assert (await s.get(User, 103)).role == "admin"


async def test_revision_queue_uses_constant_number_of_queries(client):
    await make_user(client, 104, "editor")
    await make_user(client, 105, "admin")
    async with SessionLocal() as s:
        card_ids = (await s.execute(select(Card.id).order_by(Card.id).limit(5))).scalars().all()
    for card_id in card_ids:
        await client.post(
            "/api/admin/revisions",
            json={"card_id": card_id, "payload": {"kind": "word", "be": "x", "ru": "y"}},
            headers=headers(104),
        )

    statements = []
    listener = lambda *args: statements.append(args[2])  # noqa: E731
    event.listen(engine.sync_engine, "before_cursor_execute", listener)
    try:
        r = await client.get("/api/admin/revisions", headers=headers(105))
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", listener)

    assert len(r.json()) == 5 and all(item["current"] for item in r.json())
    revision_queries = [q for q in statements if "card_revisions" in q or "FROM cards" in q or "FROM users" in q]
    assert len(revision_queries) <= 4  # правки + авторы + карточки (+ пользователь запроса), а не 2 на правку
