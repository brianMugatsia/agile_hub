"""Isolated local demo settings backed by a disposable SQLite database."""
from .development import *  # noqa: F401,F403

DEMO_MODE = True
DEMO_DATA_ENABLED = True

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "demo.sqlite3",
        "CONN_MAX_AGE": 0,
    }
}
