"""Isolated test settings for the workflow integration suite.

The installed application keeps its normal configured database.  Only pytest
uses this module, with an in-memory SQLite database, so tests never require or
mutate the development PostgreSQL service.
"""

from .base import *  # noqa: F401,F403

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

# Keep test execution deterministic and fast without changing production.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

# Phase 3A.1 test compatibility
ALLOW_HEADER_PRINCIPAL_AUTH = True
VRIDHI_AUTH_COOKIE_SECURE = False
