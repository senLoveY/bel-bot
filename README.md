# Зярнятка

Telegram-бот + Mini App: каждый день новое белорусское слово, традиция или факт.

- `backend/` — FastAPI (API для Mini App), aiogram-бот, очередь рассылки (`app/delivery.py`)
- `webapp/` — React + Vite Mini App
- `backend/app/data/cards.json` — контент (**черновик, требует вычитки носителем языка**)

## Быстрый старт (локально)

```bash
cp .env.example .env          # впишите BOT_TOKEN от @BotFather
cd webapp && npm install && npm run build && cd ..
cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.api:app --port 8000     # API + Mini App
.venv/bin/python -m app.bot                   # бот + планировщик (в другом терминале)
.venv/bin/python -m pytest                    # тесты
```

Mini App требует HTTPS: поднимите туннель (`cloudflared tunnel --url http://localhost:8000` или ngrok),
впишите адрес в `WEBAPP_URL`, а в @BotFather → Bot Settings → Menu Button задайте тот же URL.
Без Telegram интерфейс можно посмотреть так: `DEV_AUTH=true` и `http://localhost:8000/?dev=1`.

## Docker (Postgres)

```bash
docker compose up --build
```

## Как работает рассылка

1. Каждые 30 с планировщик находит пользователей, у которых наступило локальное время отправки
   (окно догонки — 6 ч), и создаёт запись `deliveries` (уникальна на пользователя и день).
2. Воркер берёт `pending`-записи и отправляет с общим лимитом 25 сообщений/с.
3. `429` — пауза на `retry_after` для всех отправок; `403` — пользователь помечается неактивным;
   сетевые ошибки — повтор с экспоненциальной задержкой (до 5 попыток).

## Дальше

SRS-повторение, озвучка, квизы, джиттер времени рассылки, Alembic-миграции, Redis при росте аудитории.
