"""Application configuration for the work context."""

from __future__ import annotations

from django.apps import AppConfig


class WorkConfig(AppConfig):
    """C7 — Work Management"""

    name = "contexts.work"
    label = "ctx_work"
    verbose_name = "C7 Work Management"
