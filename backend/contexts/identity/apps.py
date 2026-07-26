"""Application configuration for the identity context."""

from __future__ import annotations

from django.apps import AppConfig


class IdentityConfig(AppConfig):
    """C2 — Identity & Access"""

    name = "contexts.identity"
    label = "ctx_identity"
    verbose_name = "C2 Identity & Access"
