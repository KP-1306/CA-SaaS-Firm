"""Application configuration for the documents context."""

from __future__ import annotations

from django.apps import AppConfig


class DocumentsConfig(AppConfig):
    """C10 — Documents"""

    name = "contexts.documents"
    label = "ctx_documents"
    verbose_name = "C10 Documents"
