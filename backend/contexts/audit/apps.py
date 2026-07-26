"""Application configuration for the audit context."""

from __future__ import annotations

from django.apps import AppConfig


class AuditConfig(AppConfig):
    """C12 — Audit"""

    name = "contexts.audit"
    label = "ctx_audit"
    verbose_name = "C12 Audit"
