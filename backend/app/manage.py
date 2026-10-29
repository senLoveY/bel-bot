"""Команды обслуживания.

    python -m app.manage setup           # таблицы, миграции, новые карточки, роли админов
    python -m app.manage set-webhook     # направить Telegram на {WEBAPP_URL}/api/telegram/webhook
    python -m app.manage webhook-info    # проверить, куда Telegram шлёт обновления и были ли ошибки
    python -m app.manage delete-webhook  # вернуть polling (для локального бота)
    python -m app.manage set-commands    # меню команд в Telegram (админам — ещё /admin)
"""
from __future__ import annotations

import asyncio
import sys

from aiogram.types import BotCommand, BotCommandScopeChat, BotCommandScopeDefault

from .bot import make_bot
from .config import settings
from .setup import setup_database


def webhook_url() -> str:
    return f"{settings.webapp_url.rstrip('/')}/api/telegram/webhook"


async def set_webhook() -> None:
    if not settings.webhook_secret:
        raise SystemExit("WEBHOOK_SECRET is not set")
    async with make_bot() as bot:
        await bot.set_webhook(
            webhook_url(),
            secret_token=settings.webhook_secret,
            allowed_updates=["message", "callback_query"],
        )
    print(f"webhook set: {webhook_url()}")


async def webhook_info() -> None:
    async with make_bot() as bot:
        info = await bot.get_webhook_info()
    print(f"url: {info.url or '(none — polling)'}")
    print(f"pending updates: {info.pending_update_count}")
    if info.last_error_message:
        print(f"last error: {info.last_error_message}")


async def delete_webhook() -> None:
    async with make_bot() as bot:
        await bot.delete_webhook()
    print("webhook deleted: bot can use polling again")


USER_COMMANDS = [
    BotCommand(command="start", description="Пачаць і атрымаць картку дня"),
    BotCommand(command="word", description="Картка дня зараз"),
    BotCommand(command="settings", description="Налады рассылкі"),
    BotCommand(command="stop", description="Спыніць рассылку"),
]
ADMIN_COMMANDS = USER_COMMANDS + [BotCommand(command="admin", description="Увайсці ў адмін-панэль")]


async def set_commands() -> None:
    """Меню команд: всем — пользовательские, админам из ADMIN_IDS в личном чате — ещё /admin."""
    async with make_bot() as bot:
        await bot.set_my_commands(USER_COMMANDS, scope=BotCommandScopeDefault())
        for admin_id in sorted(settings.admin_id_set):
            await bot.set_my_commands(ADMIN_COMMANDS, scope=BotCommandScopeChat(chat_id=admin_id))
    print(f"commands set: {len(USER_COMMANDS)} for everyone, +/admin for {len(settings.admin_id_set)} admin(s)")


COMMANDS = {
    "setup": setup_database,
    "set-webhook": set_webhook,
    "webhook-info": webhook_info,
    "delete-webhook": delete_webhook,
    "set-commands": set_commands,
}


def main(argv: list) -> None:
    if len(argv) != 1 or argv[0] not in COMMANDS:
        raise SystemExit(f"usage: python -m app.manage {{{'|'.join(COMMANDS)}}}")
    asyncio.run(COMMANDS[argv[0]]())


if __name__ == "__main__":
    main(sys.argv[1:])
