import os
import tempfile

# настройки должны быть заданы до импорта приложения
_tmp = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_tmp}/test.db"
os.environ["BOT_TOKEN"] = "123456:TEST"
os.environ["DEV_AUTH"] = "true"

import pytest_asyncio  # noqa: E402

from app.cards import seed_cards  # noqa: E402
from app.db import Base, SessionLocal, engine  # noqa: E402
from app import models  # noqa: E402,F401


@pytest_asyncio.fixture(autouse=True)
async def fresh_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    async with SessionLocal() as session:
        await seed_cards(session)
    yield
