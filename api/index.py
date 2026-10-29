"""Точка входа Vercel: serverless-функция Python отдаёт FastAPI-приложение из backend/app."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.api import app  # noqa: E402,F401
