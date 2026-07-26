"""Application configuration for the workflow context."""

from __future__ import annotations

from django.apps import AppConfig


class WorkflowConfig(AppConfig):
    """C6 — Workflow"""

    name = "contexts.workflow"
    label = "ctx_workflow"
    verbose_name = "C6 Workflow"
