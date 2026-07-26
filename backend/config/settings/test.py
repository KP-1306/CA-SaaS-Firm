"""Automated test settings.

No database connection is opened by the bootstrap test suite. Tests that need a
database will be introduced by the work package that adds the schema, and will
declare that need explicitly through pytest-django's database fixtures.
"""

from __future__ import annotations

from typing import Any, cast

from .base import *

DEBUG = False

# Fixed, non-secret value: tests must be deterministic and this key never
# protects anything. It is not a credential.
SECRET_KEY = "test-only-key-not-a-credential-and-never-deployed"  # noqa: S105

ALLOWED_HOSTS = ["testserver", "localhost", "127.0.0.1"]

# Faster, deterministic hashing for tests only.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# Silence console logging noise during test runs. LOGGING is inherited from
# base via star import; its values are inferred as ``object``, so the nested
# mapping is narrowed with a cast before assignment. Runtime behaviour is
# unchanged: the root logger level remains WARNING.
_root_logging = cast(dict[str, Any], LOGGING["root"])
_root_logging["level"] = "WARNING"
