from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy.exc import IntegrityError

from .api import user_today
from .cards import card_for_date, format_card_message, seed_cards
from .config import settings
from .db import SessionLocal, init_db, utcnow
from .delivery import run_scheduler
from .keyboards import card_keyboard, open_app_keyboard
from .models import Card, Delivery, SavedCard, User

router = Router()


async def get_or_create_user(session, tg_user) -> User:
    user = await session.get(User, tg_user.id)
    if user is None:
        user = User(id=tg_user.id, first_name=tg_user.first_name or "", username=tg_user.username)
        session.add(user)
    return user


async def send_today_card(message: Message, session, user: User) -> None:
    day = user_today(user)
    card = await card_for_date(session, day)
    if card is None:
        await message.answer("Пакуль няма карткаў.")
        return
    await message.answer(format_card_message(card, user.explain_lang or "ru"), reply_markup=card_keyboard(card.id), parse_mode="HTML")
    # помечаем сегодняшнюю рассылку выполненной, чтобы не прислать то же самое второй раз
    session.add(Delivery(user_id=user.id, card_id=card.id, local_date=day.isoformat(), status="sent", sent_at=utcnow()))
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()


@router.message(Command("start"))
async def cmd_start(message: Message) -> None:
    async with SessionLocal() as session:
        user = await get_or_create_user(session, message.from_user)
        user.is_active = True
        await session.commit()
        await message.answer(
            f"Прывітанне, {message.from_user.first_name}! 👋 Вітаем у Зярнятцы.\n\n"
            "Я буду штодня дасылаць новае беларускае слова, цікавы факт або народнае свята. "
            f"Час дастаўкі зараз — <b>{user.send_time}</b>, змяніць яго можна ў праграме.",
            reply_markup=open_app_keyboard(tab="settings", text="⚙️ Наладзіць час"),
            parse_mode="HTML",
        )
        await send_today_card(message, session, user)


@router.message(Command("word"))
async def cmd_word(message: Message) -> None:
    async with SessionLocal() as session:
        user = await get_or_create_user(session, message.from_user)
        card = await card_for_date(session, user_today(user))
        await session.commit()
        if card is None:
            await message.answer("Пакуль няма карткаў.")
            return
        await message.answer(format_card_message(card, user.explain_lang or "ru"), reply_markup=card_keyboard(card.id), parse_mode="HTML")


@router.message(Command("settings"))
async def cmd_settings(message: Message) -> None:
    await message.answer("Налады рассылкі:", reply_markup=open_app_keyboard(tab="settings", text="⚙️ Адкрыць налады"))


@router.message(Command("stop"))
async def cmd_stop(message: Message) -> None:
    async with SessionLocal() as session:
        user = await get_or_create_user(session, message.from_user)
        user.is_active = False
        await session.commit()
    await message.answer("Рассылка спынена. Каб вярнуцца, націсніце /start.")


@router.callback_query(F.data.startswith(("save:", "known:")))
async def on_card_button(call: CallbackQuery) -> None:
    action, raw_id = call.data.split(":", 1)
    card_id = int(raw_id)
    status = "saved" if action == "save" else "learned"
    async with SessionLocal() as session:
        await get_or_create_user(session, call.from_user)
        if await session.get(Card, card_id) is None:
            await call.answer("Картка не знойдзена")
            return
        await session.flush()
        row = await session.get(SavedCard, (call.from_user.id, card_id))
        if row is None:
            session.add(SavedCard(user_id=call.from_user.id, card_id=card_id, status=status))
        else:
            row.status = status
        await session.commit()
    await call.answer("Захавана ⭐" if status == "saved" else "Малайчына! ✅")


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    if not settings.bot_token:
        raise SystemExit("BOT_TOKEN is not set")
    await init_db()
    async with SessionLocal() as session:
        await seed_cards(session)

    bot = Bot(settings.bot_token, default=DefaultBotProperties(parse_mode="HTML"))
    dp = Dispatcher()
    dp.include_router(router)
    scheduler = asyncio.create_task(run_scheduler(bot))
    try:
        await dp.start_polling(bot)
    finally:
        scheduler.cancel()


if __name__ == "__main__":
    asyncio.run(main())
