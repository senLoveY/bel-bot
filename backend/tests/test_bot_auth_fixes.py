"""Регрессионные тесты: экранирование имени, гонка при создании пользователя, общая подготовка базы."""
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from app import auth, bot
from app.config import settings
from app.db import SessionLocal
from app.models import User


def fake_message(uid: int, first_name: str, text: str = "/start"):
    msg = MagicMock(text=text, answer=AsyncMock())
    msg.from_user = SimpleNamespace(id=uid, first_name=first_name, username=None)
    return msg


async def test_greeting_escapes_html_in_first_name():
    """Раньше имя с < > & ломало HTML-разметку, и Telegram отклонял приветствие."""
    msg = fake_message(80, "<b>Ala & Co")
    await bot.cmd_start(msg)
    greeting = msg.answer.await_args_list[0].args[0]
    assert "&lt;b&gt;Ala &amp; Co" in greeting
    assert "<b>Ala" not in greeting


async def add_user(uid: int) -> None:
    async with SessionLocal() as s:
        s.add(User(id=uid, first_name="Existing"))
        await s.commit()


def pretend_first_lookup_missed(session):
    """Первый session.get «не видит» пользователя, как если бы его создали параллельно сразу после проверки."""
    real_get = session.get
    calls = {"n": 0}

    async def get(model, key, *a, **kw):
        calls["n"] += 1
        if model is User and calls["n"] == 1:
            return None
        return await real_get(model, key, *a, **kw)

    session.get = get


async def test_bot_user_creation_race_returns_existing_user():
    await add_user(81)
    async with SessionLocal() as session:
        pretend_first_lookup_missed(session)
        user = await bot.get_or_create_user(session, SimpleNamespace(id=81, first_name="New", username=None))
    assert user.id == 81 and user.first_name == "Existing"


async def test_api_user_creation_race_returns_existing_user():
    await add_user(82)
    async with SessionLocal() as session:
        pretend_first_lookup_missed(session)
        user = await auth.current_user(x_telegram_init_data="", x_dev_user="82", admin_session=None, session=session)
    assert user.id == 82 and user.first_name == "Existing"


async def test_polling_mode_uses_shared_database_setup(monkeypatch):
    """Локальный бот готовит базу так же, как API: миграции, карточки и роли из ADMIN_IDS."""
    from app import setup

    prepared = AsyncMock()
    monkeypatch.setattr(setup, "setup_database", prepared)
    monkeypatch.setattr(settings, "bot_token", "123:abc")
    monkeypatch.setattr(bot, "make_bot", MagicMock())
    monkeypatch.setattr(bot, "run_scheduler", AsyncMock())
    monkeypatch.setattr(bot, "get_dispatcher", lambda: MagicMock(start_polling=AsyncMock()))
    await bot.main()
    prepared.assert_awaited_once()
