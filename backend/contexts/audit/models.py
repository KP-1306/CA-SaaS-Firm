"""Append-only audit trail (basic, production-quality).

Audit rows are written only by the backend capture helper (never through a
generic create API) and are read-only through the viewer. Sensitive values are
sanitized before storage; file contents are never stored.
"""

from __future__ import annotations

from django.db import models

from core.db.models import TenantModel


class AuditAction(models.TextChoices):
    CREATE = "CREATE", "Record created"
    UPDATE = "UPDATE", "Record updated"
    DELETE = "DELETE", "Record deleted"
    OWNER_ASSIGNED = "OWNER_ASSIGNED", "Owner assigned"
    REVIEWER_ASSIGNED = "REVIEWER_ASSIGNED", "Reviewer assigned"
    STATUS_CHANGE = "STATUS_CHANGE", "Status changed"
    COMMENT_CREATED = "COMMENT_CREATED", "Comment created"
    DOCUMENT_REQUEST_CREATED = "DOCUMENT_REQUEST_CREATED", "Document request created"
    DOCUMENT_UPLOAD = "DOCUMENT_UPLOAD", "Document uploaded"
    ATTACHMENT_ACCEPTED = "ATTACHMENT_ACCEPTED", "Attachment accepted"
    ATTACHMENT_REJECTED = "ATTACHMENT_REJECTED", "Attachment rejected"


class AuditEvent(TenantModel):
    actor_principal_id = models.UUIDField(null=True, blank=True, db_index=True)
    actor_employee_id = models.UUIDField(null=True, blank=True)
    action = models.CharField(max_length=30, choices=AuditAction.choices, db_index=True)
    entity_type = models.CharField(max_length=60, db_index=True)
    entity_id = models.UUIDField(db_index=True)
    summary = models.CharField(max_length=300, blank=True)
    previous_values = models.JSONField(default=dict, blank=True)
    new_values = models.JSONField(default=dict, blank=True)
    correlation_id = models.CharField(max_length=64, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant_id", "created_at"]),
            models.Index(fields=["tenant_id", "entity_type", "entity_id"]),
            models.Index(fields=["tenant_id", "action"]),
        ]
