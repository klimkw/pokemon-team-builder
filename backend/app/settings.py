"""Environment configuration shared by the API and migration runner."""
import os

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql+asyncpg://pokemon:pokemon@localhost:5432/pokemon")
APP_ORIGIN = os.environ.get("APP_ORIGIN", "http://localhost:8000")
COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "false").lower() == "true"
COOKIE_NAME = "pokemon_session"
SESSION_SECONDS = 60 * 60 * 24 * 7
