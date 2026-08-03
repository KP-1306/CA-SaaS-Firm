"""Application configuration for the capacity context (Employee Operations V1)."""

from __future__ import annotations

from django.apps import AppConfig


class CapacityConfig(AppConfig):
    """Capacity, availability, leave and holidays."""

    name = "contexts.capacity"
    label = "ctx_capacity"
    verbose_name = "Capacity and Availability"
