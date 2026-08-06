"""Shared Django settings.

Deliberately minimal. This module is imported by every environment-specific
settings module and must not contain development conveniences or production
credentials.

Scope note (EWP-000.1A §5): authentication, sessions, tenant isolation,
row-level security, audit, Celery, Redis, S3, SES and observability are NOT
configured here. Each is owned by a later work package.
"""

from __future__ import annotations

from pathlib import Path

import environ  # type: ignore[import-untyped]

# backend/config/settings/base.py -> backend/
BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env()

# --------------------------------------------------------------------- core --
# SECRET_KEY, DEBUG and ALLOWED_HOSTS are intentionally NOT defaulted here.
# Each environment module is responsible for supplying them, so that production
# cannot silently inherit an insecure development value (EWP-000.1A §9.4).

# -------------------------------------------------------------- application --
DJANGO_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django.contrib.staticfiles",
    # django.contrib.admin is deliberately absent.
    # The admin bypasses the tenant model and the permission layer and is never
    # installed or routed (EIB §7.4, EWP-000.1A §9.7).
]

THIRD_PARTY_APPS = [
    "rest_framework",
]

# The 15 bounded contexts of AR §4. Each package currently contains only its
# AppConfig; domain models are owned by later work packages.
CONTEXT_APPS = [
    "contexts.platform",
    "contexts.identity",
    "contexts.organisation",
    "contexts.configuration",
    "contexts.clients",
    "contexts.workflow",
    "contexts.work",
    "contexts.generation",
    "contexts.capacity",
    "contexts.assignment",
    "contexts.quality",
    "contexts.documents",
    "contexts.collaboration",
    "contexts.audit",
    "contexts.notifications",
    "contexts.insight",
    "contexts.portal",
]

LOCAL_APPS = [
    "core.health",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS + CONTEXT_APPS

# --------------------------------------------------------------- middleware --
# Minimal by design. Request-scoped tenant resolution, principal resolution,
# row-level security session variables and audit context are owned by later
# work packages and must be inserted deliberately, not inherited by default.
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
            ],
        },
    },
]

# ----------------------------------------------------------------- database --
# PostgreSQL is the architectural database (TAD §5): row-level security is a
# load-bearing tenant-isolation mechanism, so no other engine is permitted.
# EWP-000.1A opens no connection; provisioning is a later work package.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env.str("POSTGRES_DB", default="cafirm_dev"),
        "USER": env.str("POSTGRES_USER", default="cafirm_app"),
        "PASSWORD": env.str("POSTGRES_PASSWORD", default=""),
        "HOST": env.str("POSTGRES_HOST", default="localhost"),
        "PORT": env.int("POSTGRES_PORT", default=5432),
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ------------------------------------------------------ internationalisation --
LANGUAGE_CODE = "en-gb"
# All timestamps are stored in UTC (TD §1.3). Display-time zone conversion is a
# presentation concern owned by a later work package.
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# ------------------------------------------------------------------- static --
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# --------------------------------------------------------------------- DRF --
# Defaults are intentionally restrictive. Authentication and permission classes
# are supplied by the work package that implements the authorisation model
# (TD §7.4); until then no endpoint may rely on a permissive default.
REST_FRAMEWORK: dict[str, object] = {
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "UNAUTHENTICATED_USER": None,
}

# ------------------------------------------------------------------ logging --
# Bootstrap logging only: console output, no external transport, no request
# body capture. Structured logging with sensitive-field redaction is owned by
# the observability work package (EIB §4.11).
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "simple": {"format": "{levelname} {name} {message}", "style": "{"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "simple"},
    },
    "root": {"handlers": ["console"], "level": "INFO"},
}

from .media import *  # noqa: F401,F403  workflow media settings

# --- Phase 3A.1 Vridhi consultant authentication policy ---
VRIDHI_PROVIDER_TENANT_ID = env.str(
    "VRIDHI_PROVIDER_TENANT_ID",
    default="11111111-1111-1111-1111-111111111111",
)
VRIDHI_SESSION_AGE_SECONDS = env.int(
    "VRIDHI_SESSION_AGE_SECONDS",
    default=43_200,
)
VRIDHI_MAX_LOGIN_FAILURES = env.int(
    "VRIDHI_MAX_LOGIN_FAILURES",
    default=5,
)
VRIDHI_LOGIN_LOCK_SECONDS = env.int(
    "VRIDHI_LOGIN_LOCK_SECONDS",
    default=900,
)
ALLOW_HEADER_PRINCIPAL_AUTH = False
VRIDHI_AUTH_COOKIE_SECURE = True
