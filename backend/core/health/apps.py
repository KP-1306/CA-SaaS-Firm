"""Application configuration for the health endpoint."""

from __future__ import annotations

from django.apps import AppConfig


class HealthConfig(AppConfig):
    """Bootstrap health endpoint."""

    name = "core.health"
    label = "core_health"
    verbose_name = "Health"
