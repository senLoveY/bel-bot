# Зярнятка

Telegram-бот + Mini App: каждый день новое белорусское слово, традиция или факт.

- `backend/` — FastAPI (API для Mini App), aiogram-бот, очередь рассылки (`app/delivery.py`)
- `webapp/` — React + Vite Mini App
- `backend/app/data/cards.json` — контент (**черновик, требует вычитки носителем языка**)

## Быстрый старт (локально)

```bash
cp .env.example .env          # впишите BOT_TOKEN от @BotFather
cd webapp && npm install && cd ..
cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt && cd ..
./scripts/dev.sh                                  # API + Mini App на http://localhost:8000/?dev=1
cd backend && .venv/bin/python -m pytest          # тесты бэкенда
cd webapp && npm test                             # тесты фронтенда
```

`scripts/dev.sh` поднимает API и Mini App на отдельной SQLite-базе с входом по `?dev=<id>`
(`?dev=1` — админ). Бота локально обычно не запускают: в продакшене он работает через webhook.
Если нужно отладить бота локально: `python -m app.manage delete-webhook`, затем `python -m app.bot`
(polling); после — снова `set-webhook`, иначе продакшен-бот перестанет получать сообщения.
Чтобы кнопки Mini App в Telegram открывали локальную версию, нужен HTTPS-туннель на `:8000`
и его адрес в `WEBAPP_URL`.

## Продакшен на Vercel

Один проект Vercel с двумя сервисами (`vercel.json`):

| Сервис | Папка | Что это | Публичный путь |
|---|---|---|---|
| `backend` | `backend/` | FastAPI (`main.py`), все маршруты под `/api` | `/api/*` |
| `webapp` | `webapp/` | Vite: Mini App (`/`) и сайт админки (`/admin`) | всё остальное |

Сервисы не вызывают друг друга напрямую: браузер ходит на `/api/...` того же домена, поэтому bindings не нужны.

1. **Vercel → Add New Project →** импорт репозитория, корень — корень репозитория.
2. **Environment Variables** (для сервиса `backend`):
   `BOT_TOKEN`, `DATABASE_URL` (Supabase Session pooler, префикс `postgresql+asyncpg://`),
   `WEBAPP_URL` (публичный адрес проекта, например `https://zyarnyatka.vercel.app`), `ADMIN_IDS`,
   `SERVERLESS=true`, `WEBHOOK_SECRET`, `CRON_SECRET`.
3. После деплоя направить Telegram на webhook и задать меню команд (из `backend/`, с теми же
   `WEBAPP_URL`, `WEBHOOK_SECRET`, `ADMIN_IDS`): `python -m app.manage set-webhook`,
   `python -m app.manage set-commands`; проверка — `python -m app.manage webhook-info`.
   Диагностика без секретов: `GET /api/health`.
4. **Крон:** раз в 5 минут `POST {WEBAPP_URL}/api/cron/tick` с заголовком
   `Authorization: Bearer <CRON_SECRET>` (например, cron-job.org). Вручную — workflow «Broadcast tick».

Локально оба сервиса вместе: `vercel dev`. Без Vercel CLI: `./scripts/dev.sh`.
Локальный бот работает через polling: перед запуском `python -m app.manage delete-webhook`,
после — снова `set-webhook`, иначе продакшен-бот перестанет получать сообщения.

## Миграции базы (Alembic)

Схема описана в `backend/app/models.py`, миграции — в `backend/migrations/versions/`.
Приложение применяет их само при старте (на Vercel — при первом запросе). Новая миграция после
изменения моделей: из `backend/` выполнить `alembic revision --autogenerate -m "что изменилось"`
и проверить файл. Тест `test_migrations_match_models` падает, если модели и миграции разошлись.

## Как работает рассылка

1. Каждые 30 с (локально) или при каждом вызове крона (Vercel) планировщик находит пользователей, у которых наступило локальное время отправки
   (окно догонки — 6 ч), и создаёт запись `deliveries` (уникальна на пользователя и день).
2. Воркер берёт `pending`-записи и отправляет с общим лимитом 25 сообщений/с.
3. `429` — пауза на `retry_after` для всех отправок; `403` — пользователь помечается неактивным;
   сетевые ошибки — повтор с экспоненциальной задержкой (до 5 попыток).

## Дальше

SRS-повторение, озвучка, квизы, джиттер времени рассылки, Alembic-миграции, Redis при росте аудитории.
