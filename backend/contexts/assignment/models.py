"""Assignment and reviewer-hierarchy models (Employee Operations V1).

Approved decisions 5, 10, 11:

* **Layered reviewer hierarchy** — ``ReviewerRule`` rows attach at one of several
  scopes (assignment/service/task-template/team/employee-default/partner
  fallback). Resolution picks the most specific applicable rule (service layer).
* **Transient recommendations** — recommendations are computed on demand and are
  NOT stored. Only the approved outcome is persisted as an ``AssignmentDecision``
  (with override status, reason and the explanation snapshot).
* **Append-only history** — every applied assignment/reassignment writes an
  immutable ``AssignmentEvent``.

All models are tenant-scoped ``TenantModel`` subclasses using UUID references.
"""

from __future__ import annotations

from django.db import models

from core.db.models import TenantModel


class ReviewerScope(models.TextChoices):
    ASSIGNMENT = "ASSIGNMENT", "Assignment-specific"
    SERVICE = "SERVICE", "Service"
    TASK_TEMPLATE = "TASK_TEMPLATE", "Task template"
    TEAM = "TEAM", "Team"
    EMPLOYEE_DEFAULT = "EMPLOYEE_DEFAULT", "Employee default"
    PARTNER_FALLBACK = "PARTNER_FALLBACK", "Partner/final fallback"


class ReviewerLevel(models.TextChoices):
    PRIMARY = "PRIMARY", "Primary reviewer"
    SECONDARY = "SECONDARY", "Secondary reviewer"
    ESCALATION = "ESCALATION", "Escalation reviewer"
    FINAL_APPROVER = "FINAL_APPROVER", "Final approver"


class ReviewerRule(TenantModel):
    """One configurable reviewer mapping at a given scope and level.

    ``scope`` + ``scope_ref_id`` identify what the rule attaches to (e.g. a
    service id, task-template id, team id, employee id, or a specific work item
    for ASSIGNMENT scope). ``reviewer_user_id`` is the employee who reviews at
    ``level``. Effective-dated and de-activatable. Not every level need exist;
    resolution simply uses whatever is configured, most-specific-scope first.
    """

    scope = models.CharField(max_length=20, choices=ReviewerScope.choices, db_index=True)
    scope_ref_id = models.UUIDField(null=True, blank=True, db_index=True)
    level = models.CharField(max_length=15, choices=ReviewerLevel.choices, default=ReviewerLevel.PRIMARY)
    reviewer_user_id = models.UUIDField(db_index=True)
    service_id = models.UUIDField(null=True, blank=True, db_index=True)
    effective_from = models.DateField(null=True, blank=True)
    effective_to = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    notes = models.CharField(max_length=200, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["tenant_id", "scope", "scope_ref_id", "level"],
                condition=models.Q(is_active=True),
                name="uq_active_reviewer_rule",
            )
        ]
        ordering = ["scope", "level"]
        indexes = [models.Index(
                fields=["tenant_id", "scope", "is_active"],
                name="ix_revrule_scope_active",
            )]


class AssignmentDecision(TenantModel):
    """The persisted, approved assignment outcome for a work item.

    Recommendations themselves are transient; this row records only what a
    permitted human approved: the selected owner/reviewer, whether it overrode
    the top recommendation, the reason, and the explanation snapshot (JSON) that
    was shown at decision time. Append-friendly: a reassignment writes a new
    decision; the latest active one is authoritative.
    """

    work_item_id = models.UUIDField(db_index=True)
    selected_owner_user_id = models.UUIDField(null=True, blank=True, db_index=True)
    selected_reviewer_user_id = models.UUIDField(null=True, blank=True, db_index=True)
    was_override = models.BooleanField(default=False)
    override_reason = models.TextField(blank=True)
    recommended_owner_user_id = models.UUIDField(null=True, blank=True)
    explanation = models.JSONField(default=dict, blank=True)
    decided_by = models.UUIDField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(
                fields=["tenant_id", "work_item_id", "is_active"],
                name="ix_assndecision_wi_active",
            )]


class AssignmentEventType(models.TextChoices):
    RECOMMENDED_APPLIED = "RECOMMENDED_APPLIED", "Recommended assignment applied"
    OVERRIDE_APPLIED = "OVERRIDE_APPLIED", "Override assignment applied"
    REASSIGNED = "REASSIGNED", "Reassigned"
    REVIEWER_SET = "REVIEWER_SET", "Reviewer set"


class AssignmentEvent(TenantModel):
    """Append-only assignment history ledger.

    One immutable row per applied assignment action. Never updated or deleted by
    the application; it is the queryable operational trail (distinct from the
    generic AuditEvent, which remains the compliance record).
    """

    work_item_id = models.UUIDField(db_index=True)
    event_type = models.CharField(max_length=25, choices=AssignmentEventType.choices)
    owner_user_id = models.UUIDField(null=True, blank=True)
    reviewer_user_id = models.UUIDField(null=True, blank=True)
    was_override = models.BooleanField(default=False)
    reason = models.TextField(blank=True)
    actor_user_id = models.UUIDField(null=True, blank=True)
    detail = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(
                fields=["tenant_id", "work_item_id"],
                name="ix_assnevent_wi",
            )]
