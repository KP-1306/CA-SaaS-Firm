"""Shared pytest configuration.

The bootstrap suite opens no database connection. Tests that require a database
will declare that need explicitly through pytest-django's `db` fixture once the
schema exists (a later work package).
"""

from __future__ import annotations
