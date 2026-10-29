from datetime import date

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.api import create_app
from app.cards import card_for_date, seed_cards
from app.db import SessionLocal
from app.models import Card, CardRevision, User


def headers(uid: int) -> dict:
    return {"X-Dev-User": str(uid)}


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=create_app()), base_url="http://t") as c:
        yield c


async def make_user(client, uid: int, role: str) -> None:
    await client.get("/api/me", headers=headers(uid))  # создаёт пользователя
    async with SessionLocal() as s:
        user = await s.get(User, uid)
        user.role = role
        await s.commit()


async def first_word_id() -> int:
    async with SessionLocal() as s:
        return (await s.execute(select(Card.id).where(Card.kind == "word").order_by(Card.id))).scalars().first()


async def test_regular_user_gets_403(client):
    await make_user(client, 10, "user")
    assert (await client.get("/api/admin/stats", headers=headers(10))).status_code == 403


async def test_editor_proposes_admin_approves(client):
    await make_user(client, 11, "editor")
    await make_user(client, 12, "admin")
    card_id = await first_word_id()

    r = await client.post(
        "/api/admin/revisions",
        json={"card_id": card_id, "payload": {"kind": "word", "be": "прывітанне", "ru": "привет, здравствуй"}},
        headers=headers(11),
    )
    assert r.status_code == 201
    rev_id = r.json()["id"]

    # редактор не может одобрять
    assert (await client.post(f"/api/admin/revisions/{rev_id}/approve", headers=headers(11))).status_code == 403

    # админ одобряет — изменение применяется
    approved = await client.post(f"/api/admin/revisions/{rev_id}/approve", headers=headers(12))
    assert approved.status_code == 200
    assert approved.json()["ru"] == "привет, здравствуй"

    # повторное одобрение — конфликт
    assert (await client.post(f"/api/admin/revisions/{rev_id}/approve", headers=headers(12))).status_code == 409


async def test_author_cannot_approve_own_revision(client):
    # правка, отправленная редактором, который потом стал админом, всё равно ждёт другого админа
    await make_user(client, 13, "editor")
    rev = await client.post(
        "/api/admin/revisions",
        json={"payload": {"kind": "fact", "be": "Факт", "ru": "Текст факта"}},
        headers=headers(13),
    )
    assert rev.json()["status"] == "pending"
    await make_user(client, 13, "admin")
    assert (await client.post(f"/api/admin/revisions/{rev.json()['id']}/approve", headers=headers(13))).status_code == 403


async def test_admin_edit_is_applied_immediately(client):
    await make_user(client, 21, "admin")
    card_id = await first_word_id()
    r = await client.post(
        "/api/admin/revisions",
        json={"card_id": card_id, "payload": {"kind": "word", "be": "прывітанне", "ru": "здравствуйте"}},
        headers=headers(21),
    )
    assert r.status_code == 201
    assert r.json()["status"] == "approved"
    assert r.json()["card"]["ru"] == "здравствуйте"
    async with SessionLocal() as s:
        assert (await s.get(Card, card_id)).ru == "здравствуйте"
        rev = await s.get(CardRevision, r.json()["id"])
        assert rev.reviewer_id == 21 and rev.reviewed_at is not None  # история правок сохраняется

    pending = (await client.get("/api/admin/revisions?status=pending", headers=headers(21))).json()
    assert all(p["id"] != r.json()["id"] for p in pending)


async def test_admin_new_card_is_created_and_published_immediately(client):
    await make_user(client, 22, "admin")
    r = await client.post(
        "/api/admin/revisions", json={"payload": {"kind": "fact", "be": "Новы факт", "ru": "Описание"}}, headers=headers(22)
    )
    card = r.json()["card"]
    assert card["published"] is True
    listed = (await client.get("/api/cards?kind=fact&limit=200", headers=headers(77))).json()
    assert any(c["id"] == card["id"] for c in listed)


async def test_reject_keeps_card_unchanged(client):
    await make_user(client, 14, "editor")
    await make_user(client, 15, "admin")
    card_id = await first_word_id()
    rev = await client.post(
        "/api/admin/revisions",
        json={"card_id": card_id, "payload": {"kind": "word", "be": "ЗМЕНА", "ru": "ЗМЕНА"}},
        headers=headers(14),
    )
    await client.post(
        f"/api/admin/revisions/{rev.json()['id']}/reject", json={"note": "не то"}, headers=headers(15)
    )
    async with SessionLocal() as s:
        assert (await s.get(Card, card_id)).be != "ЗМЕНА"
        assert (await s.get(CardRevision, rev.json()["id"])).status == "rejected"


async def test_revision_validation(client):
    await make_user(client, 16, "editor")
    bad_kind = {"payload": {"kind": "poem", "be": "x", "ru": "y"}}
    missing = {"payload": {"kind": "fact", "be": "x"}}
    bad_md = {"payload": {"kind": "holiday", "be": "x", "ru": "y", "month_day": "13-45"}}
    for body in (bad_kind, missing, bad_md):
        assert (await client.post("/api/admin/revisions", json=body, headers=headers(16))).status_code == 422


async def test_unpublished_card_hidden_from_users(client):
    await make_user(client, 17, "admin")
    card_id = await first_word_id()
    await client.put(f"/api/admin/cards/{card_id}/published", json={"published": False}, headers=headers(17))

    listed = (await client.get("/api/cards?kind=word", headers=headers(77))).json()
    assert all(c["id"] != card_id for c in listed)
    assert (await client.get(f"/api/cards/{card_id}", headers=headers(77))).status_code == 404


async def test_schedule_overrides_rotation(client):
    await make_user(client, 18, "admin")
    card_id = await first_word_id()
    day = "2026-04-01"
    r = await client.put("/api/admin/schedule", json={"day": day, "card_id": card_id}, headers=headers(18))
    assert r.status_code == 200

    async with SessionLocal() as s:
        chosen = await card_for_date(s, date(2026, 4, 1))
        assert chosen.id == card_id


async def test_schedule_rejects_unpublished_card(client):
    await make_user(client, 19, "admin")
    card_id = await first_word_id()
    await client.put(f"/api/admin/cards/{card_id}/published", json={"published": False}, headers=headers(19))
    r = await client.put("/api/admin/schedule", json={"day": "2026-04-02", "card_id": card_id}, headers=headers(19))
    assert r.status_code == 422


async def test_admin_cannot_demote_self(client):
    await make_user(client, 20, "admin")
    r = await client.put("/api/admin/users/20/role", json={"role": "user"}, headers=headers(20))
    assert r.status_code == 400


async def test_seed_does_not_overwrite_existing_cards():
    async with SessionLocal() as s:
        card = await s.get(Card, await first_word_id())
        card.be = "ЗМЕНЕНА"
        await s.commit()
        assert await seed_cards(s) == 0
        await s.refresh(card)
        assert card.be == "ЗМЕНЕНА"
