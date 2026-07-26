"""Application configuration for the configuration context."""

from __future__ import annotations

from django.apps import AppConfig


class ConfigurationConfig(AppConfig):
    """C4 — Configuration"""

    name = "contexts.configuration"
    label = "ctx_configuration"
    verbose_name = "C4 Configuration"
