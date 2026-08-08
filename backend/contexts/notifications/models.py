from __future__ import annotations

from django.db import models

from core.db.models import TenantModel


class NotificationType(models.TextChoices):
    WORK_ASSIGNED = "WORK_ASSIGNED", "Work assigned"
    REVIEW_REQUESTED = "REVIEW_REQUESTED", "Review requested"
    REWORK_REQUESTED = "REWORK_REQUESTED", "Rework requested"
    WORK_COMPLETED = "WORK_COMPLETED", "Work completed"


class Notification(TenantModel):
    recipient_principal_id = models.UUIDField(db_index=True)

    notification_type = models.CharField(
        max_length=40,
        choices=NotificationType.choices,
        db_index=True,
    )

    title = models.CharField(max_length=160)
    message = models.CharField(max_length=500, blank=True)

    entity_type = models.CharField(
        max_length=60,
        blank=True,
        db_index=True,
    )
    entity_id = models.UUIDField(
        null=True,
        blank=True,
        db_index=True,
    )

    read_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
    )

    metadata = models.JSONField(
        default=dict,
        blank=True,
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=[
                    "tenant_id",
                    "recipient_principal_id",
                    "read_at",
                ],
            ),
            models.Index(
                fields=[
                    "tenant_id",
                    "notification_type",
                    "created_at",
                ],
            ),
        ]
