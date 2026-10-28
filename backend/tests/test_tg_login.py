from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app import auth, bot
from app.api import create_app
from app.db import SessionLocal
from app.models import User


def headers(uid: int) -> dict:
    return {"X-Dev-User": str(uid)}


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=create_app()), base_url="http://t") as c:
        yield c


async def set_role(uid: int, role: str) -> None:
    async with SessionLocal() as s:
        user = await s.get(User, uid)
        if user is None:
            s.add(User(id=uid, first_name="Ala", role=role))
        else:
            user.role = role
        await s.commit()


def token_from(url: str) -> str:
    return url.split("token=", 1)[1]


async def test_login_link_grants_session_and_redirects(client):
    await set_role(60, "admin")
    r = await client.get(f"/api/web/tg-login?token={auth.make_login_token(60)}", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/admin"
    assert "admin_session" in r.cookies

    stats = await client.get("/api/admin/stats", headers={"Cookie": f"admin_session={r.cookies['admin_session']}"})
    assert stats.status_code == 200


async def test_link_works_only_once(client):
    await set_role(61, "editor")
    token = auth.make_login_token(61)
    first = await client.get(f"/api/web/tg-login?token={token}", follow_redirects=False)
    second = await client.get(f"/api/web/tg-login?token={token}", follow_redirects=False)
    assert first.status_code == 303
    assert second.status_code == 401


async def test_expired_link_rejected(client, monkeypatch):
    await set_role(62, "admin")
    monkeypatch.setattr(auth, "LOGIN_TTL", -5)
    token = auth.make_login_token(62)
    assert (await client.get(f"/api/web/tg-login?token={token}", follow_redirects=False)).status_code == 401


async def test_tampered_link_rejected(client):
    await set_role(63, "admin")
    token = auth.make_login_token(63)
    forged = token.replace("63.", "64.", 1)
    assert (await client.get(f"/api/web/tg-login?token={forged}", follow_redirects=False)).status_code == 401


async def test_plain_user_link_is_forbidden(client):
    await set_role(65, "user")
    token = auth.make_login_token(65)
    assert (await client.get(f"/api/web/tg-login?token={token}", follow_redirects=False)).status_code == 403


async def test_malformed_token_rejected(client):
    assert (await client.get("/api/web/tg-login?token=abc", follow_redirects=False)).status_code == 401


async def test_logout_endpoint_clears_session(client):
    out = await client.post("/api/web/logout")
    assert out.status_code == 200
    assert "admin_session" in out.headers.get("set-cookie", "")


def fake_message(uid: int, text: str = "/admin"):
    msg = MagicMock()
    msg.text = text
    msg.from_user = SimpleNamespace(id=uid, first_name="Ala", username="ala")
    msg.answer = AsyncMock()
    return msg


async def test_admin_command_refuses_regular_user():
    await set_role(70, "user")
    msg = fake_message(70)
    await bot.cmd_admin(msg)
    msg.answer.assert_awaited_once_with("У вас няма доступу да адмін-панэлі.")


async def test_admin_command_sends_one_time_link_to_editor():
    await set_role(71, "editor")
    msg = fake_message(71)
    await bot.cmd_admin(msg)
    kwargs = msg.answer.await_args.kwargs
    url = kwargs["reply_markup"].inline_keyboard[0][0].url
    assert "/api/web/tg-login?token=" in url
    assert auth.read_login_token(token_from(url)) == 71


async def test_start_with_admin_payload_sends_login_link():
    await set_role(72, "admin")
    msg = fake_message(72, text="/start admin")
    await bot.cmd_start(msg)
    assert "reply_markup" in msg.answer.await_args.kwargs
    assert "tg-login" in msg.answer.await_args.kwargs["reply_markup"].inline_keyboard[0][0].url


async def test_start_without_payload_still_greets_user():
    msg = fake_message(73, text="/start")
    await bot.cmd_start(msg)
    assert msg.answer.await_count == 2
    async with SessionLocal() as s:
        assert (await s.execute(select(User).where(User.id == 73))).scalar_one()
