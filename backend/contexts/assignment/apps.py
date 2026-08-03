"""Application configuration for the assignment context (Employee Operations V1)."""

from __future__ import annotations

from django.apps import AppConfig


class AssignmentConfig(AppConfig):
    """Assignment eligibility, deterministic recommendations and reviewer rules."""

    name = "contexts.assignment"
    label = "ctx_assignment"
    verbose_name = "Assignment and Reviewer Hierarchy"
