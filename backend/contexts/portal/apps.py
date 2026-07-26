"""Application configuration for the portal context."""

from __future__ import annotations

from django.apps import AppConfig


class PortalConfig(AppConfig):
    """C15 — Portal Publication"""

    name = "contexts.portal"
    label = "ctx_portal"
    verbose_name = "C15 Portal Publication"
