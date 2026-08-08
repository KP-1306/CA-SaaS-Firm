#!/usr/bin/env python
"""Django administrative command entry point."""

from __future__ import annotations

import os
import sys


def main() -> None:
    """Run an administrative task."""
    # Development is the default so that a bare `python manage.py ...` never
    # accidentally runs against production settings.
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development_postgres")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:  # pragma: no cover - import guard
        raise ImportError(
            "Django could not be imported. Activate the virtual environment and "
            "install dependencies: pip install -r requirements/development.txt"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
