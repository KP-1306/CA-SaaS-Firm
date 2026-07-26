"""Application configuration for the insight context."""

from __future__ import annotations

from django.apps import AppConfig


class InsightConfig(AppConfig):
    """C14 — Insight"""

    name = "contexts.insight"
    label = "ctx_insight"
    verbose_name = "C14 Insight"
