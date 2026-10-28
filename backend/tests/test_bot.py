from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from sqlalchemy import delete, select

from app import bot
from app.config import settings
from app.db import SessionLocal
from app.keyboards import card_keyboard, open_app_keyboard, webapp_url
from app.models import Card, Delivery, SavedCard, User


def fake_message(uid: int, name: str = "Ala"):
    msg = MagicMock()
    msg.from_user = SimpleNamespace(id=uid, first_name=name, username="ala")
    msg.answer = AsyncMock()
    return msg


def fake_call(data: str, uid: int):
    call = MagicMock()
    call.data = data
    call.from_user = SimpleNamespace(id=uid, first_name="Ala", username="ala")
    call.answer = AsyncMock()
    return call


async def first_card_id() -> int:
    async with SessionLocal() as s:
        return (await s.execute(select(Card.id).order_by(Card.id))).scalars().first()


async def test_start_registers_user_and_sends_card():
    msg = fake_message(5)
    await bot.cmd_start(msg)
    async with SessionLocal() as s:
        user = await s.get(User, 5)
        assert user.is_active
        assert (await s.execute(select(Delivery).where(Delivery.user_id == 5))).scalars().first() is not None
    assert msg.answer.await_count == 2  # приветствие и карточка


async def test_second_start_same_day_does_not_crash():
    await bot.cmd_start(fake_message(6))
    # на сегодня уже есть запись рассылки: повторная вставка не должна ронять обработчик
    await bot.cmd_start(fake_message(6))
    async with SessionLocal() as s:
        rows = (await s.execute(select(Delivery).where(Delivery.user_id == 6))).scalars().all()
        assert len(rows) == 1


async def test_word_command_returns_card():
    msg = fake_message(7)
    await bot.cmd_word(msg)
    assert msg.answer.await_count == 1


async def test_word_command_without_cards():
    async with SessionLocal() as s:
        await s.execute(delete(Card))
        await s.commit()
    msg = fake_message(8)
    await bot.cmd_word(msg)
    msg.answer.assert_awaited_once_with("Пакуль няма карткаў.")


async def test_settings_and_stop_commands():
    msg = fake_message(9)
    await bot.cmd_settings(msg)
    msg.answer.assert_awaited_once()

    await bot.cmd_start(fake_message(9))
    await bot.cmd_stop(fake_message(9))
    async with SessionLocal() as s:
        assert (await s.get(User, 9)).is_active is False


async def test_save_then_learned_buttons_update_same_row():
    card_id = await first_card_id()

    await bot.on_card_button(fake_call(f"save:{card_id}", uid=10))
    async with SessionLocal() as s:
        assert (await s.get(SavedCard, (10, card_id))).status == "saved"

    call = fake_call(f"known:{card_id}", uid=10)
    await bot.on_card_button(call)
    async with SessionLocal() as s:
        assert (await s.get(SavedCard, (10, card_id))).status == "learned"
    call.answer.assert_awaited_once_with("Малайчына! ✅")


async def test_button_for_missing_card_is_reported():
    call = fake_call("save:99999", uid=11)
    await bot.on_card_button(call)
    call.answer.assert_awaited_once_with("Картка не знойдзена")


def test_card_keyboard_has_app_and_action_buttons():
    kb = card_keyboard(3)
    assert len(kb.inline_keyboard) == 2
    assert kb.inline_keyboard[0][0].web_app.url == webapp_url(3)
    assert kb.inline_keyboard[1][0].callback_data == "save:3"


def test_webapp_url_params():
    base = settings.webapp_url
    assert webapp_url() == base
    assert webapp_url(card_id=5, tab="settings") == f"{base}?card=5&tab=settings"
    kb = open_app_keyboard(tab="settings", text="Налады")
    assert kb.inline_keyboard[0][0].text == "Налады"
    assert kb.inline_keyboard[0][0].web_app.url == f"{base}?tab=settings"
