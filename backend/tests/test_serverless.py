import runpy
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.pool import NullPool

from app import manage, setup, webhook
from app.api import create_app
from app.config import settings
from app.db import engine_kwargs

UPDATE = {
    "update_id": 1,
    "message": {
        "message_id": 1,
        "date": 1700000000,
        "chat": {"id": 5, "type": "private"},
        "from": {"id": 5, "is_bot": False, "first_name": "Ala"},
        "text": "/start",
    },
}


class FakeBot:
    """Заменяет aiogram.Bot: поддерживает async with и записывает вызовы API."""

    def __init__(self):
        self.set_webhook = AsyncMock()
        self.delete_webhook = AsyncMock()
        self.get_webhook_info = AsyncMock(
            return_value=MagicMock(url="https://x/api/telegram/webhook", pending_update_count=0, last_error_message="boom")
        )

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=create_app()), base_url="http://t") as c:
        yield c


@pytest.fixture
def secrets(monkeypatch):
    monkeypatch.setattr(settings, "webhook_secret", "hook-secret")
    monkeypatch.setattr(settings, "cron_secret", "cron-secret")
    monkeypatch.setattr(webhook, "make_bot", FakeBot)


async def test_webhook_rejects_missing_or_wrong_secret(client, secrets):
    assert (await client.post("/api/telegram/webhook", json=UPDATE)).status_code == 401
    bad = {"X-Telegram-Bot-Api-Secret-Token": "nope"}
    assert (await client.post("/api/telegram/webhook", json=UPDATE, headers=bad)).status_code == 401


async def test_webhook_disabled_when_secret_not_configured(client, monkeypatch):
    monkeypatch.setattr(settings, "webhook_secret", "")
    r = await client.post("/api/telegram/webhook", json=UPDATE, headers={"X-Telegram-Bot-Api-Secret-Token": ""})
    assert r.status_code == 401


async def test_webhook_feeds_update_to_dispatcher(client, secrets, monkeypatch):
    dp = MagicMock(feed_update=AsyncMock())
    monkeypatch.setattr(webhook, "get_dispatcher", lambda: dp)
    r = await client.post("/api/telegram/webhook", json=UPDATE, headers={"X-Telegram-Bot-Api-Secret-Token": "hook-secret"})
    assert r.status_code == 200
    update = dp.feed_update.await_args.args[1]
    assert update.update_id == 1 and update.message.text == "/start"


async def test_webhook_handler_error_still_returns_200(client, secrets, monkeypatch):
    dp = MagicMock(feed_update=AsyncMock(side_effect=RuntimeError("handler failed")))
    monkeypatch.setattr(webhook, "get_dispatcher", lambda: dp)
    r = await client.post("/api/telegram/webhook", json=UPDATE, headers={"X-Telegram-Bot-Api-Secret-Token": "hook-secret"})
    assert r.status_code == 200  # иначе Telegram будет повторять обновление


async def test_cron_requires_bearer_secret(client, secrets):
    assert (await client.post("/api/cron/tick")).status_code == 401
    assert (await client.post("/api/cron/tick", headers={"Authorization": "Bearer nope"})).status_code == 401


async def test_cron_disabled_when_secret_not_configured(client, monkeypatch):
    monkeypatch.setattr(settings, "cron_secret", "")
    assert (await client.post("/api/cron/tick", headers={"Authorization": "Bearer "})).status_code == 401


async def test_cron_enqueues_and_sends_a_batch(client, secrets, monkeypatch):
    enqueue = AsyncMock(return_value=3)
    process = AsyncMock(return_value=2)
    monkeypatch.setattr(webhook, "enqueue_due", enqueue)
    monkeypatch.setattr(webhook, "process_pending", process)
    r = await client.post("/api/cron/tick", headers={"Authorization": "Bearer cron-secret"})
    assert r.json() == {"enqueued": 3, "processed": 2}
    assert process.await_args.kwargs["batch"] == settings.cron_batch


async def test_ensure_ready_runs_setup_once_in_serverless(monkeypatch):
    calls = AsyncMock()
    monkeypatch.setattr(setup, "setup_database", calls)
    monkeypatch.setattr(setup, "_ready", False)

    monkeypatch.setattr(settings, "serverless", False)
    await setup.ensure_ready()
    assert calls.await_count == 0  # обычный сервер готовит базу при старте

    monkeypatch.setattr(settings, "serverless", True)
    await setup.ensure_ready()
    await setup.ensure_ready()
    assert calls.await_count == 1


async def test_setup_database_is_idempotent():
    await setup.setup_database()
    await setup.setup_database()


def test_engine_kwargs_for_serverless_postgres():
    kw = engine_kwargs("postgresql+asyncpg://u:p@host:5432/db", serverless=True)
    assert kw["poolclass"] is NullPool
    args = kw["connect_args"]
    assert args["statement_cache_size"] == 0
    assert args["prepared_statement_name_func"]() != args["prepared_statement_name_func"]()


def test_engine_kwargs_for_local_sqlite():
    assert engine_kwargs("sqlite+aiosqlite:///./data/app.db", serverless=False) == {}


async def test_set_webhook_requires_secret(monkeypatch):
    monkeypatch.setattr(settings, "webhook_secret", "")
    with pytest.raises(SystemExit):
        await manage.set_webhook()


async def test_set_webhook_points_telegram_to_our_url(monkeypatch, capsys):
    bot = FakeBot()
    monkeypatch.setattr(manage, "make_bot", lambda: bot)
    monkeypatch.setattr(settings, "webhook_secret", "hook-secret")
    monkeypatch.setattr(settings, "webapp_url", "https://zyarnyatka.vercel.app/")
    await manage.set_webhook()
    args, kwargs = bot.set_webhook.await_args
    assert args[0] == "https://zyarnyatka.vercel.app/api/telegram/webhook"
    assert kwargs["secret_token"] == "hook-secret"
    assert "webhook set" in capsys.readouterr().out


async def test_webhook_info_and_delete(monkeypatch, capsys):
    bot = FakeBot()
    monkeypatch.setattr(manage, "make_bot", lambda: bot)
    await manage.webhook_info()
    await manage.delete_webhook()
    out = capsys.readouterr().out
    assert "last error: boom" in out and "webhook deleted" in out
    bot.delete_webhook.assert_awaited_once()


def test_manage_rejects_unknown_command():
    with pytest.raises(SystemExit):
        manage.main(["deploy"])


def test_vercel_entrypoint_exposes_fastapi_app():
    entry = Path(__file__).resolve().parents[1] / "main.py"  # entrypoint сервиса backend в vercel.json
    app = runpy.run_path(str(entry))["app"]
    assert app.title == "Belarusian Daily"
    assert any(getattr(r, "path", "") == "/api/telegram/webhook" for r in app.routes)
