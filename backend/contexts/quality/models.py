from __future__ import annotations

from django.db import models

from core.db.models import TenantModel


class QAChecklistStatus(models.TextChoices):
    DRAFT = "DRAFT", "Draft"
    ACTIVE = "ACTIVE", "Active"
    RETIRED = "RETIRED", "Retired"


class QAResponseValue(models.TextChoices):
    PENDING = "PENDING", "Pending"
    YES = "YES", "Yes"
    NO = "NO", "No"
    NOT_APPLICABLE = "NOT_APPLICABLE", "Not applicable"


class QAReviewCycleStatus(models.TextChoices):
    PREPARATION = "PREPARATION", "Preparation"
    READY_FOR_REVIEW = "READY_FOR_REVIEW", "Ready for review"
    IN_REVIEW = "IN_REVIEW", "In review"
    CHANGES_REQUESTED = "CHANGES_REQUESTED", "Changes requested"
    RESUBMITTED = "RESUBMITTED", "Resubmitted"
    APPROVED = "APPROVED", "Approved"
    CLOSED = "CLOSED", "Closed"


class QAIssueStatus(models.TextChoices):
    OPEN = "OPEN", "Open"
    RESOLVED = "RESOLVED", "Resolved"
    REOPENED = "REOPENED", "Reopened"
    WAIVED = "WAIVED", "Waived"


class QAIssueSeverity(models.TextChoices):
    LOW = "LOW", "Low"
    MEDIUM = "MEDIUM", "Medium"
    HIGH = "HIGH", "High"
    CRITICAL = "CRITICAL", "Critical"


class ServiceQAChecklistSet(TenantModel):
    service_id = models.UUIDField(db_index=True)
    name = models.CharField(max_length=180)
    version_number = models.PositiveIntegerField(default=1)
    status = models.CharField(
        max_length=10,
        choices=QAChecklistStatus.choices,
        default=QAChecklistStatus.DRAFT,
        db_index=True,
    )
    effective_from = models.DateField(null=True, blank=True, db_index=True)
    effective_until = models.DateField(null=True, blank=True, db_index=True)
    description = models.TextField(blank=True)
    require_preparer_confirmation = models.BooleanField(default=True)
    require_reviewer_confirmation = models.BooleanField(default=True)
    require_final_approval = models.BooleanField(default=False)
    prevent_self_review = models.BooleanField(default=True)

    class Meta:
        ordering = ["service_id", "-version_number", "-effective_from"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant_id", "service_id", "version_number"],
                name="uq_qaset_service_version",
            )
        ]
        indexes = [
            models.Index(
                fields=["tenant_id", "service_id", "status"],
                name="idx_qaset_service_status",
            )
        ]


class ServiceQAChecklistItem(TenantModel):
    checklist_set_id = models.UUIDField(db_index=True)
    service_id = models.UUIDField(db_index=True)
    code = models.CharField(max_length=60)
    title = models.CharField(max_length=220)
    description = models.TextField(blank=True)
    guidance = models.TextField(blank=True)
    display_order = models.PositiveIntegerField(default=10)
    mandatory = models.BooleanField(default=True, db_index=True)
    preparer_required = models.BooleanField(default=True)
    reviewer_required = models.BooleanField(default=True)
    evidence_required = models.BooleanField(default=False)
    allow_not_applicable = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        ordering = ["display_order", "title"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant_id", "checklist_set_id", "code"],
                name="uq_qaitem_set_code",
            )
        ]
        indexes = [
            models.Index(
                fields=["tenant_id", "checklist_set_id", "display_order"],
                name="idx_qaitem_set_order",
            )
        ]


class QAReviewCycle(TenantModel):
    work_item_id = models.UUIDField(db_index=True)
    service_id = models.UUIDField(null=True, blank=True, db_index=True)
    checklist_set_id = models.UUIDField(null=True, blank=True, db_index=True)
    checklist_version = models.PositiveIntegerField(default=0)
    cycle_number = models.PositiveIntegerField(default=1)
    status = models.CharField(
        max_length=20,
        choices=QAReviewCycleStatus.choices,
        default=QAReviewCycleStatus.PREPARATION,
        db_index=True,
    )
    owner_user_id = models.UUIDField(null=True, blank=True, db_index=True)
    reviewer_user_id = models.UUIDField(null=True, blank=True, db_index=True)
    final_approver_user_id = models.UUIDField(null=True, blank=True, db_index=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    review_started_at = models.DateTimeField(null=True, blank=True)
    changes_requested_at = models.DateTimeField(null=True, blank=True)
    resubmitted_at = models.DateTimeField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    submission_comment = models.TextField(blank=True)
    review_comment = models.TextField(blank=True)
    approval_comment = models.TextField(blank=True)
    checklist_snapshot = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = ["-cycle_number", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant_id", "work_item_id", "cycle_number"],
                name="uq_qacycle_work_number",
            )
        ]
        indexes = [
            models.Index(
                fields=["tenant_id", "work_item_id", "status"],
                name="idx_qacycle_work_status",
            ),
            models.Index(
                fields=["tenant_id", "reviewer_user_id", "status"],
                name="idx_qacycle_reviewer_status",
            ),
        ]


class QAReviewResponse(TenantModel):
    review_cycle_id = models.UUIDField(db_index=True)
    work_item_id = models.UUIDField(db_index=True)
    checklist_item_id = models.UUIDField(null=True, blank=True, db_index=True)
    checklist_item_code = models.CharField(max_length=60)
    checklist_item_title = models.CharField(max_length=220)
    mandatory = models.BooleanField(default=True)
    preparer_response = models.CharField(
        max_length=20,
        choices=QAResponseValue.choices,
        default=QAResponseValue.PENDING,
        db_index=True,
    )
    preparer_comment = models.TextField(blank=True)
    preparer_evidence_attachment_id = models.UUIDField(null=True, blank=True)
    preparer_completed_by = models.UUIDField(null=True, blank=True)
    preparer_completed_at = models.DateTimeField(null=True, blank=True)
    reviewer_response = models.CharField(
        max_length=20,
        choices=QAResponseValue.choices,
        default=QAResponseValue.PENDING,
        db_index=True,
    )
    reviewer_comment = models.TextField(blank=True)
    reviewer_evidence_attachment_id = models.UUIDField(null=True, blank=True)
    reviewer_completed_by = models.UUIDField(null=True, blank=True)
    reviewer_completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["checklist_item_code", "created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant_id", "review_cycle_id", "checklist_item_code"],
                name="uq_qaresponse_cycle_code",
            )
        ]


class QAReviewIssue(TenantModel):
    review_cycle_id = models.UUIDField(db_index=True)
    work_item_id = models.UUIDField(db_index=True)
    response_id = models.UUIDField(null=True, blank=True, db_index=True)
    document_request_id = models.UUIDField(null=True, blank=True, db_index=True)
    attachment_id = models.UUIDField(null=True, blank=True, db_index=True)
    category = models.CharField(max_length=60, blank=True)
    severity = models.CharField(
        max_length=10,
        choices=QAIssueSeverity.choices,
        default=QAIssueSeverity.MEDIUM,
        db_index=True,
    )
    status = models.CharField(
        max_length=10,
        choices=QAIssueStatus.choices,
        default=QAIssueStatus.OPEN,
        db_index=True,
    )
    title = models.CharField(max_length=220)
    description = models.TextField()
    raised_by = models.UUIDField()
    assigned_to = models.UUIDField(null=True, blank=True, db_index=True)
    due_date = models.DateField(null=True, blank=True)
    resolution_comment = models.TextField(blank=True)
    resolved_by = models.UUIDField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["tenant_id", "work_item_id", "status"],
                name="idx_qaissue_work_status",
            ),
            models.Index(
                fields=["tenant_id", "assigned_to", "status"],
                name="idx_qaissue_assignee",
            ),
        ]
