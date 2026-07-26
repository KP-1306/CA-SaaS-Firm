"""Application configuration for the collaboration context."""

from __future__ import annotations

from django.apps import AppConfig


class CollaborationConfig(AppConfig):
    """C11 — Collaboration"""

    name = "contexts.collaboration"
    label = "ctx_collaboration"
    verbose_name = "C11 Collaboration"
