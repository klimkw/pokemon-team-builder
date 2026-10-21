"""Environment configuration shared by the API and migration runner."""
import os

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql+asyncpg://pokemon:pokemon@localhost:5432/pokemon")
APP_ORIGIN = os.environ.get("APP_ORIGIN", "http://localhost:8000")
COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "false").lower() == "true"
COOKIE_NAME = os.environ.get("COOKIE_NAME", "pokemon_session")
SESSION_SECONDS = 60 * 60 * 24 * 7


def positive_setting(name: str, default: int) -> int:
    value = os.environ.get(name, str(default))
    if not value.isascii() or not value.isdecimal() or int(value) <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return int(value)


CATALOG_SCAN_INTERVAL_HOURS = positive_setting("CATALOG_SCAN_INTERVAL_HOURS", 24)
CHANGE_ALERT_WINDOW_DAYS = positive_setting("CHANGE_ALERT_WINDOW_DAYS", 7)

# Labels the isolated fixture environment; does not enable demo HTTP mutations.
DEMO_MODE = os.environ.get("DEMO_MODE", "false") == "true"

ENABLE_DEMO_CONTROLS = os.environ.get("ENABLE_DEMO_CONTROLS", "false") == "true"

# Local Compose keeps its durable worker; free hosting may run bounded demos inline.
DEMO_EXECUTION_MODE = os.environ.get("DEMO_EXECUTION_MODE", "worker")
if DEMO_EXECUTION_MODE not in ("worker", "request"):
    raise ValueError("DEMO_EXECUTION_MODE must be worker or request")
