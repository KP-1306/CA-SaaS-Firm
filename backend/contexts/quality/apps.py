"""Application configuration for the quality context."""

from __future__ import annotations

from django.apps import AppConfig


class QualityConfig(AppConfig):
    """C9 — Quality"""

    name = "contexts.quality"
    label = "ctx_quality"
    verbose_name = "C9 Quality"
