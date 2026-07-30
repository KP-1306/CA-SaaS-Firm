from __future__ import annotations

import uuid

from django.db import models

from core.db.models import TenantModel


class WorkStatus(models.TextChoices):
    NOT_STARTED = "NOT_STARTED", "Not started"
    IN_PROGRESS = "IN_PROGRESS", "In progress"
    WAITING_FOR_CLIENT = "WAITING_FOR_CLIENT", "Waiting for client"
    READY_FOR_REVIEW = "READY_FOR_REVIEW", "Ready for review"
    REWORK_REQUIRED = "REWORK_REQUIRED", "Rework required"
    COMPLETED = "COMPLETED", "Completed"
    CANCELLED = "CANCELLED", "Cancelled"


class WorkPriority(models.TextChoices):
    LOW = "LOW", "Low"
    NORMAL = "NORMAL", "Normal"
    HIGH = "HIGH", "High"
    URGENT = "URGENT", "Urgent"


class WorkItem(TenantModel):
    """A single unit of client work owned by one employee and optionally reviewed.

    References to client, service and employees are UUID columns, never foreign
    keys, matching the cross-context convention (TD 2.1): integrity is on
    ``(tenant_id, id)`` pairs. Serializers expose read-only ``*_name`` fields so
    the UI never handles raw UUIDs.
    """

    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    client_id = models.UUIDField(db_index=True)
    service_id = models.UUIDField(null=True, blank=True, db_index=True)
    owner_user_id = models.UUIDField(null=True, blank=True, db_index=True)
    reviewer_user_id = models.UUIDField(null=True, blank=True, db_index=True)
    period = models.CharField(max_length=40, blank=True)
    due_date = models.DateField(null=True, blank=True)
    status = models.CharField(
        max_length=20, choices=WorkStatus.choices, default=WorkStatus.NOT_STARTED, db_index=True
    )
    priority = models.CharField(
        max_length=10, choices=WorkPriority.choices, default=WorkPriority.NORMAL
    )
    review_comment = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    submitted_for_review_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["due_date", "-created_at"]


class WorkNote(TenantModel):
    """An append-only history/comment entry against a work item."""

    work_item_id = models.UUIDField(db_index=True)
    author_user_id = models.UUIDField(null=True, blank=True)
    entry = models.TextField()
    from_status = models.CharField(max_length=20, blank=True)
    to_status = models.CharField(max_length=20, blank=True)

    class Meta:
        ordering = ["-created_at"]


class DocumentRequestStatus(models.TextChoices):
    REQUESTED = "REQUESTED", "Requested"
    PARTIALLY_RECEIVED = "PARTIALLY_RECEIVED", "Partially received"
    RECEIVED = "RECEIVED", "Received"
    ACCEPTED = "ACCEPTED", "Accepted"
    REJECTED = "REJECTED", "Rejected"
    WAIVED = "WAIVED", "Waived"


class DocumentChannel(models.TextChoices):
    WHATSAPP = "WHATSAPP", "WhatsApp"
    EMAIL = "EMAIL", "Email"
    PORTAL = "PORTAL", "Portal"
    PHONE = "PHONE", "Phone"
    MANUAL = "MANUAL", "Manual"


class AttachmentSource(models.TextChoices):
    CLIENT = "CLIENT", "Client"
    INTERNAL_TEAM = "INTERNAL_TEAM", "Internal team"
    EMAIL = "EMAIL", "Email"
    WHATSAPP = "WHATSAPP", "WhatsApp"
    PORTAL = "PORTAL", "Portal"
    PHYSICAL_SCAN = "PHYSICAL_SCAN", "Physical scan"
    OTHER = "OTHER", "Other"


class AttachmentReviewStatus(models.TextChoices):
    PENDING_REVIEW = "PENDING_REVIEW", "Pending review"
    ACCEPTED = "ACCEPTED", "Accepted"
    REJECTED = "REJECTED", "Rejected"
    SUPERSEDED = "SUPERSEDED", "Superseded"


class DocumentRequest(TenantModel):
    """A document expected from a client, optionally tied to a work item.

    ``mandatory`` requests in a non-terminal state block work completion.
    ``received_date`` is set automatically when status becomes RECEIVED.
    """

    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    client_id = models.UUIDField(db_index=True)
    work_item_id = models.UUIDField(null=True, blank=True, db_index=True)
    requested_date = models.DateField(null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    received_date = models.DateField(null=True, blank=True)
    requested_from_contact_id = models.UUIDField(null=True, blank=True, db_index=True)
    request_channel = models.CharField(max_length=12, choices=DocumentChannel.choices, default=DocumentChannel.WHATSAPP)
    sent_at = models.DateTimeField(null=True, blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    verified_by = models.UUIDField(null=True, blank=True)
    verification_comment = models.TextField(blank=True)
    status = models.CharField(
        max_length=20,
        choices=DocumentRequestStatus.choices,
        default=DocumentRequestStatus.REQUESTED,
        db_index=True,
    )
    mandatory = models.BooleanField(default=False)
    client_visible = models.BooleanField(default=True)
    remarks = models.TextField(blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["due_date", "-created_at"]


def _attachment_upload_to(instance: "DocumentAttachment", filename: str) -> str:
    """Tenant-scoped storage path. Never exposed to the frontend."""
    parent = instance.document_request_id or instance.work_item_id or "unlinked"
    return f"attachments/{instance.tenant_id}/{parent}/{uuid.uuid4()}_{filename}"


class DocumentAttachment(TenantModel):
    """A received file attached to a document request.

    Stored through Django's storage abstraction under a tenant-scoped path.
    The raw filesystem path is never serialized; download is via an authorised
    backend endpoint only.
    """

    document_request_id = models.UUIDField(null=True, blank=True, db_index=True)
    work_item_id = models.UUIDField(null=True, blank=True, db_index=True)
    source = models.CharField(max_length=20, choices=AttachmentSource.choices, default=AttachmentSource.INTERNAL_TEAM)
    uploaded_by = models.UUIDField(null=True, blank=True)
    original_name = models.CharField(max_length=255)
    content_type = models.CharField(max_length=120, blank=True)
    size_bytes = models.PositiveIntegerField(default=0)
    file = models.FileField(upload_to=_attachment_upload_to)
    review_status = models.CharField(
        max_length=20,
        choices=AttachmentReviewStatus.choices,
        default=AttachmentReviewStatus.PENDING_REVIEW,
        db_index=True,
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.UUIDField(null=True, blank=True)
    review_comment = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]

def recalculate_document_request_status(
    document_request: "DocumentRequest",
    *,
    updated_by=None,
    save: bool = True,
) -> str:
    """Derive and optionally persist request status from attachment review state.

    WAIVED remains an explicit request-level override during C2 compatibility.
    Every other state is derived from the attachment lifecycle.
    """
    if document_request.status == DocumentRequestStatus.WAIVED:
        derived = DocumentRequestStatus.WAIVED
    else:
        states = list(
            DocumentAttachment.objects.filter(
                tenant_id=document_request.tenant_id,
                document_request_id=document_request.id,
            ).values_list("review_status", flat=True)
        )
        if AttachmentReviewStatus.ACCEPTED in states:
            derived = DocumentRequestStatus.ACCEPTED
        elif AttachmentReviewStatus.PENDING_REVIEW in states:
            derived = DocumentRequestStatus.PARTIALLY_RECEIVED
        elif states:
            derived = DocumentRequestStatus.RECEIVED
        else:
            derived = DocumentRequestStatus.REQUESTED

    changed_fields = []
    if document_request.status != derived:
        document_request.status = derived
        changed_fields.append("status")
    if updated_by is not None and document_request.updated_by != updated_by:
        document_request.updated_by = updated_by
        changed_fields.append("updated_by")

    if save and changed_fields:
        changed_fields.append("row_version")
        document_request.save(update_fields=changed_fields)
    return derived


def document_request_is_complete(document_request: "DocumentRequest") -> bool:
    """A request is complete only when waived or backed by an accepted attachment."""
    if document_request.status == DocumentRequestStatus.WAIVED:
        return True
    return DocumentAttachment.objects.filter(
        tenant_id=document_request.tenant_id,
        document_request_id=document_request.id,
        review_status=AttachmentReviewStatus.ACCEPTED,
    ).exists()
