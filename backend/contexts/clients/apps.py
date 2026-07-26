"""Application configuration for the clients context."""

from __future__ import annotations

from django.apps import AppConfig


class ClientsConfig(AppConfig):
    """C5 — Client"""

    name = "contexts.clients"
    label = "ctx_clients"
    verbose_name = "C5 Client"
