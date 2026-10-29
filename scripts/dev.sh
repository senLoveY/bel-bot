#!/usr/bin/env bash
# Локальный запуск API + Mini App на отдельной SQLite-базе с dev-входом (?dev=<id>).
# Бот здесь не запускается: он работает на Fly, второй экземпляр с тем же токеном даст конфликт polling.
set -euo pipefail
cd "$(dirname "$0")/.."

(cd webapp && npm run build >/dev/null)

cd backend
export DEV_AUTH=true                       # только локально: сервер слушает 127.0.0.1
export ADMIN_IDS="${ADMIN_IDS:-1}"         # ?dev=1 получает роль admin
export DATABASE_URL="sqlite+aiosqlite:///./data/dev.db"
exec .venv/bin/uvicorn app.api:app --host 127.0.0.1 --port "${PORT:-8000}" --reload
