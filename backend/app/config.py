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
    send_jitter_min: int = 10  # каждому пользователю сдвигаем время на ±N минут, чтобы не слать всем в одну секунду

    # Telegram ID через запятую: при старте им выдаётся роль admin
    admin_ids: str = ""

    @property
    def admin_id_set(self) -> set[int]:
        return {int(x) for x in self.admin_ids.split(",") if x.strip().isdigit()}
    max_attempts: int = 5


settings = Settings()
