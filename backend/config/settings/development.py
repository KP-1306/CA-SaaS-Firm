"""Local development settings.

Never used in production. Convenience defaults live here and nowhere else, so
that production cannot inherit them (EWP-000.1A §9).
"""

from __future__ import annotations

from .base import *
from .base import env

DEBUG = True

# Development-only fallback. Production supplies this from the secret store and
# fails on startup when it is absent (see production.py).
SECRET_KEY = env.str(
    "DJANGO_SECRET_KEY",
    default="django-insecure-development-only-not-for-any-deployed-environment",
)

ALLOWED_HOSTS = ["localhost", "127.0.0.1", "[::1]"]

# Explicit origins only. Wildcard CORS is prohibited (EWP-000.1A §9.8).
# The frontend dev server runs on Vite's default port.
CSRF_TRUSTED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

# ---------------------------------------------------------------------
# Local SQLite database (development only)
# ---------------------------------------------------------------------

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

# Phase 3A.1 local compatibility
ALLOW_HEADER_PRINCIPAL_AUTH = True
VRIDHI_AUTH_COOKIE_SECURE = False
