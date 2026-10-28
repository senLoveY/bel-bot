from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_ENV = Path(__file__).resolve().parents[2] / ".env"  # .env лежит в корне проекта


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT_ENV, extra="ignore")

    bot_token: str = ""
    database_url: str = "sqlite+aiosqlite:///./data/app.db"
    webapp_url: str = "https://example.com"
    dev_auth: bool = False

    default_tz: str = "Europe/Minsk"
    default_send_time: str = "09:00"

    # рассылка
    send_rate_per_sec: int = 25  # лимит Telegram ~30/сек, оставляем запас
    send_concurrency: int = 10
    scheduler_tick_sec: int = 30
    catchup_hours: int = 6  # после простоя не шлём карточку позднее, чем через N часов
    max_attempts: int = 5


settings = Settings()
