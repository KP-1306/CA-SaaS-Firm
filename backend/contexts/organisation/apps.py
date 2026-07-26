"""Application configuration for the organisation context."""

from __future__ import annotations

from django.apps import AppConfig


class OrganisationConfig(AppConfig):
    """C3 — Firm Organisation"""

    name = "contexts.organisation"
    label = "ctx_organisation"
    verbose_name = "C3 Firm Organisation"
