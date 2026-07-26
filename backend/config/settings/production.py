"""Production settings.

Fails fast and loudly. Every mandatory secret is read without a default, so a
missing value raises at import time rather than silently degrading to an
insecure fallback (EWP-000.1A §9.4).

Scope note: TLS termination, secret-store integration, observability transport
and CORS origins for the deployed frontend are owned by later work packages.
The security posture below is the floor, never to be relaxed to simplify
startup (EWP-000.1A §9.10).
"""

from __future__ import annotations

from .base import *
from .base import env

DEBUG = False

# No default. ImproperlyConfigured is raised at import time when absent.
SECRET_KEY = env.str("DJANGO_SECRET_KEY")

# No default. An empty or wildcard host list is not permitted.
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS")

# ---------------------------------------------------------------- transport --
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31_536_000  # one year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# ------------------------------------------------------------------ cookies --
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Strict"
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = "Strict"

# ------------------------------------------------------------------ headers --
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"

# Explicit origins only; never a wildcard (EWP-000.1A §9.8).
CSRF_TRUSTED_ORIGINS = env.list("DJANGO_CSRF_TRUSTED_ORIGINS", default=[])
