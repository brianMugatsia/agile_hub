"""Fast, isolated settings for the test suite."""
import tempfile
from pathlib import Path

from .base import *  # noqa: F401,F403

DEBUG = False
SECRET_KEY = "test-secret-key-not-for-production"
ALLOWED_HOSTS = ["testserver", "localhost"]

DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
MEDIA_ROOT = Path(tempfile.gettempdir()) / "boost_hub_test_media"

# Lockout and throttling have their own tests; keep them out of everyday ones.
AXES_ENABLED = False
AUTHENTICATION_BACKENDS = ["django.contrib.auth.backends.ModelBackend"]
REST_FRAMEWORK = {**REST_FRAMEWORK, "DEFAULT_THROTTLE_CLASSES": []}  # noqa: F405

LOGGING_CONFIG = None