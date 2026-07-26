"""Application configuration for the generation context."""

from __future__ import annotations

from django.apps import AppConfig


class GenerationConfig(AppConfig):
    """C8 — Work Generation"""

    name = "contexts.generation"
    label = "ctx_generation"
    verbose_name = "C8 Work Generation"
