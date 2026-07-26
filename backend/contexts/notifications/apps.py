"""Application configuration for the notifications context."""

from __future__ import annotations

from django.apps import AppConfig


class NotificationsConfig(AppConfig):
    """C13 — Notification & Escalation"""

    name = "contexts.notifications"
    label = "ctx_notifications"
    verbose_name = "C13 Notification & Escalation"
