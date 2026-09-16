"""Entorno usado por el pipeline de CI y por los tests locales."""

import os

from .base import *  # noqa: F403

DEBUG = False
ALLOWED_HOSTS = ["*"]

if os.environ.get("USE_SQLITE") == "1":
    DATABASES = {  # noqa: F405
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": ":memory:",
        }
    }

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
