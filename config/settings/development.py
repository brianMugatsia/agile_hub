"""Local development settings."""
from .base import *  # noqa: F401,F403

DEBUG = env_bool("DEBUG", True)  # noqa: F405
DEVELOPMENT_MODE = True
DEMO_DATA_ENABLED = True
SECRET_KEY = SECRET_KEY or "django-insecure-dev-only-key-change-me"  # noqa: F405
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "[::1]"]
INTERNAL_IPS = ["127.0.0.1"]

# Password-reset emails are printed in the terminal.
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"