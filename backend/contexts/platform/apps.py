"""Application configuration for the platform context."""

from __future__ import annotations

from django.apps import AppConfig


class PlatformConfig(AppConfig):
    """C1 — Platform & Tenancy"""

    name = "contexts.platform"
    label = "ctx_platform"
    verbose_name = "C1 Platform & Tenancy"
