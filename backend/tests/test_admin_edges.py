
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select

from app.api import create_app
from app.db import SessionLocal, utcnow
from app.models import Card, Delivery, User


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


async def card_id_of(kind: str) -> int:
    async with SessionLocal() as s:
        return (await s.execute(select(Card.id).where(Card.kind == kind).order_by(Card.id))).scalars().first()


async def test_admin_card_filters(client):
    await make_user(client, 40, "admin")
    everything = (await client.get("/api/admin/cards", headers=headers(40))).json()
    assert len(everything) == (await client.get("/api/admin/cards?limit=300", headers=headers(40))).json().__len__()

    words = (await client.get("/api/admin/cards?kind=word&q=вада", headers=headers(40))).json()
    assert words and all(c["kind"] == "word" for c in words)

    card_id = words[0]["id"]
    await client.put(f"/api/admin/cards/{card_id}/published", json={"published": False}, headers=headers(40))
    hidden = (await client.get("/api/admin/cards?published=false", headers=headers(40))).json()
    assert any(c["id"] == card_id for c in hidden)
    shown = (await client.get("/api/admin/cards?published=true", headers=headers(40))).json()
    assert all(c["id"] != card_id for c in shown)


async def test_publish_unknown_card_is_404(client):
    await make_user(client, 41, "admin")
    r = await client.put("/api/admin/cards/99999/published", json={"published": True}, headers=headers(41))
    assert r.status_code == 404


async def test_propose_for_missing_card_is_404(client):
    await make_user(client, 42, "editor")
    r = await client.post(
        "/api/admin/revisions", json={"card_id": 99999, "payload": {"ru": "x"}}, headers=headers(42)
    )
    assert r.status_code == 404


async def test_propose_validation_errors(client):
    await make_user(client, 43, "editor")
    cases = [
        {"payload": {"kind": "fact", "be": "x", "ru": "y", "unknown": 1}},
        {"payload": {"kind": "fact", "be": "x"}},
        {"payload": {"kind": "poem", "be": "x", "ru": "y"}},
        {"payload": {"kind": "fact", "be": "x", "ru": "y", "level": "C2"}},
        {"payload": {"kind": "fact", "be": "   ", "ru": "y"}},
        {"payload": {"kind": "fact", "be": None, "ru": "y"}},
    ]
    for body in cases:
        r = await client.post("/api/admin/revisions", json=body, headers=headers(43))
        assert r.status_code == 422, body


async def test_create_revision_with_empty_body_gets_default(client):
    await make_user(client, 44, "editor")
    await make_user(client, 45, "admin")
    rev = await client.post(
        "/api/admin/revisions",
        json={"payload": {"kind": "fact", "be": "Новы факт", "ru": "Описание", "body": None}},
        headers=headers(44),
    )
    approved = await client.post(f"/api/admin/revisions/{rev.json()['id']}/approve", headers=headers(45))
    assert approved.status_code == 200
    assert approved.json()["published"] is True
    async with SessionLocal() as s:
        card = await s.get(Card, approved.json()["id"])
        assert card.body == "" and card.slug.startswith("fact-")


async def test_approve_when_card_was_deleted_is_404(client):
    await make_user(client, 46, "editor")
    await make_user(client, 47, "admin")
    card_id = await card_id_of("fact")
    rev = await client.post(
        "/api/admin/revisions",
        json={"card_id": card_id, "payload": {"kind": "fact", "be": "x", "ru": "y"}},
        headers=headers(46),
    )
    async with SessionLocal() as s:
        await s.execute(delete(Card).where(Card.id == card_id))
        await s.commit()
    r = await client.post(f"/api/admin/revisions/{rev.json()['id']}/approve", headers=headers(47))
    assert r.status_code == 404


async def test_list_revisions_by_status_and_reject_flow(client):
    await make_user(client, 48, "editor")
    await make_user(client, 49, "admin")
    rev = await client.post(
        "/api/admin/revisions", json={"payload": {"kind": "fact", "be": "A", "ru": "B"}}, headers=headers(48)
    )
    rev_id = rev.json()["id"]

    pending = (await client.get("/api/admin/revisions?status=pending", headers=headers(49))).json()
    assert any(r["id"] == rev_id for r in pending)
    assert pending[0]["author"]

    assert (await client.post("/api/admin/revisions/99999/reject", json={}, headers=headers(49))).status_code == 404
    done = await client.post(f"/api/admin/revisions/{rev_id}/reject", json={"note": "нет"}, headers=headers(49))
    assert done.json()["status"] == "rejected"
    assert (await client.post(f"/api/admin/revisions/{rev_id}/reject", json={}, headers=headers(49))).status_code == 409

    rejected = (await client.get("/api/admin/revisions?status=rejected", headers=headers(49))).json()
    assert any(r["id"] == rev_id and r["note"] == "нет" for r in rejected)


async def test_schedule_list_set_and_clear(client):
    await make_user(client, 50, "admin")
    card_id = await card_id_of("word")

    days = (await client.get("/api/admin/schedule?days=3", headers=headers(50))).json()
    assert len(days) == 3 and all(d["card"] is None for d in days)

    day = days[0]["day"]
    assert (await client.put("/api/admin/schedule", json={"day": "2026/04/01", "card_id": card_id}, headers=headers(50))).status_code == 422
    assert (await client.put("/api/admin/schedule", json={"day": day, "card_id": 99999}, headers=headers(50))).status_code == 404

    assert (await client.put("/api/admin/schedule", json={"day": day, "card_id": card_id}, headers=headers(50))).status_code == 200
    # повторная установка обновляет строку
    assert (await client.put("/api/admin/schedule", json={"day": day, "card_id": card_id}, headers=headers(50))).status_code == 200
    listed = (await client.get("/api/admin/schedule?days=3", headers=headers(50))).json()
    assert listed[0]["card"]["id"] == card_id

    cleared = await client.delete(f"/api/admin/schedule/{day}", headers=headers(50))
    assert cleared.json()["card"] is None
    assert (await client.delete("/api/admin/schedule/2000-01-01", headers=headers(50))).status_code == 200


async def test_users_list_search_and_role_changes(client):
    await make_user(client, 51, "admin")
    await make_user(client, 52, "user")

    found = (await client.get("/api/admin/users?q=Dev", headers=headers(51))).json()
    assert isinstance(found, list)
    everyone = (await client.get("/api/admin/users", headers=headers(51))).json()
    assert any(u["id"] == 52 for u in everyone)

    assert (await client.put("/api/admin/users/52/role", json={"role": "editor"}, headers=headers(51))).json()["role"] == "editor"
    assert (await client.put("/api/admin/users/52/role", json={"role": "boss"}, headers=headers(51))).status_code == 422
    assert (await client.put("/api/admin/users/99999/role", json={"role": "editor"}, headers=headers(51))).status_code == 404


async def test_stats_report_recent_errors(client):
    await make_user(client, 53, "editor")
    card_id = await card_id_of("word")
    today = utcnow().date().isoformat()
    async with SessionLocal() as s:
        s.add(Delivery(user_id=53, card_id=card_id, local_date=today, status="failed", error="boom"))
        await s.commit()
    stats = (await client.get("/api/admin/stats", headers=headers(53))).json()
    assert stats["deliveries_last_24h"].get("failed") == 1
    assert stats["recent_errors"][0]["error"] == "boom"
    assert stats["cards_total"] >= 1 and stats["avg_streak"] >= 0


async def test_review_own_revision_blocked_for_admin_too(client):
    await make_user(client, 54, "editor")
    rev = await client.post(
        "/api/admin/revisions", json={"payload": {"kind": "fact", "be": "A", "ru": "B"}}, headers=headers(54)
    )
    await make_user(client, 54, "admin")
    assert (await client.post(f"/api/admin/revisions/{rev.json()['id']}/reject", json={}, headers=headers(54))).status_code == 403
