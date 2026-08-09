"""C8 Work Generation models — subscriptions, task templates, recurrence.

Additive to the validated baseline. Every model derives from ``TenantModel`` and
uses ``UUIDField`` for all cross-context references (never ``ForeignKey``),
matching the platform convention (TD 2.1): integrity is on ``(tenant_id, id)``.

This context owns the operational chain that precedes a WorkItem:

    Client -> ClientServiceSubscription -> TaskTemplate
          -> RecurringWorkProfile -> (generated) WorkItem + GeneratedWorkLedger

It defines NO workflow logic and mutates no existing model. Work generation is a
deterministic, idempotent foundation (see ``generation.py``): no scheduler, no
billing, no background jobs.
"""

from __future__ import annotations

from django.db import models

from core.db.models import TenantModel


class SubscriptionStatus(models.TextChoices):
    ACTIVE = "ACTIVE", "Active"
    PAUSED = "PAUSED", "Paused"
    ENDED = "ENDED", "Ended"


class RecurrenceFrequency(models.TextChoices):
    NONE = "NONE", "None"
    MONTHLY = "MONTHLY", "Monthly"
    QUARTERLY = "QUARTERLY", "Quarterly"
    HALF_YEARLY = "HALF_YEARLY", "Half yearly"
    YEARLY = "YEARLY", "Yearly"


class ClientServiceSubscription(TenantModel):
    """A client's subscription to a configured service.

    Links an existing ``Client`` to an existing ``Service`` (both by UUID). A
    subscription is the durable statement that a firm delivers a given service to
    a given client, optionally on a recurring cadence. It carries no billing.
    """

    client_id = models.UUIDField(db_index=True)
    service_id = models.UUIDField(db_index=True)
    default_owner_user_id = models.UUIDField(null=True, blank=True, db_index=True)
    default_reviewer_user_id = models.UUIDField(null=True, blank=True, db_index=True)
    frequency = models.CharField(
        max_length=15,
        choices=RecurrenceFrequency.choices,
        default=RecurrenceFrequency.NONE,
    )
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    status = models.CharField(
        max_length=10,
        choices=SubscriptionStatus.choices,
        default=SubscriptionStatus.ACTIVE,
        db_index=True,
    )
    notes = models.TextField(blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["tenant_id", "client_id", "service_id"],
                name="uq_subscription_client_service",
            )
        ]
        ordering = ["-created_at"]


class TaskTemplate(TenantModel):
    """A reusable definition for creating work items for a service.

    Provides the default title/description/priority/due-day offset used when work
    is created from the template. ``service_id`` ties the template to a
    configured service; ``default_owner_user_id`` seeds ownership.
    """

    service_id = models.UUIDField(db_index=True)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    default_title = models.CharField(max_length=200, blank=True)
    default_priority = models.CharField(max_length=10, blank=True)
    default_owner_user_id = models.UUIDField(null=True, blank=True, db_index=True)
    default_reviewer_user_id = models.UUIDField(null=True, blank=True, db_index=True)
    default_due_days = models.PositiveIntegerField(null=True, blank=True)
    default_estimated_hours = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["tenant_id", "service_id", "name"],
                name="uq_task_template_service_name",
            )
        ]
        ordering = ["name"]


class RecurringWorkProfile(TenantModel):
    """A profile that deterministically generates work items on a cadence.

    Bound to a subscription (and optionally a template). The generator
    (``generation.py``) computes a period key per due window and creates at most
    one work item per (profile, period_key) — enforced by the ledger's unique
    constraint below. No scheduler runs here; generation is invoked explicitly
    and is safe to call repeatedly (idempotent).
    """

    subscription_id = models.UUIDField(db_index=True)
    task_template_id = models.UUIDField(null=True, blank=True, db_index=True)
    client_id = models.UUIDField(db_index=True)
    service_id = models.UUIDField(db_index=True)
    frequency = models.CharField(
        max_length=15,
        choices=RecurrenceFrequency.choices,
        default=RecurrenceFrequency.MONTHLY,
    )
    anchor_date = models.DateField(null=True, blank=True)

    operational_defaults = models.JSONField(
        default=dict,
        blank=True,
        help_text=(
            "Service-specific operational values copied into "
            "generated work items."
        ),
    )

    default_owner_user_id = models.UUIDField(null=True, blank=True, db_index=True)
    default_reviewer_user_id = models.UUIDField(null=True, blank=True, db_index=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-created_at"]


class GeneratedWorkLedger(TenantModel):
    """Idempotency ledger: one row per (profile, period_key) actually generated.

    The unique constraint is the idempotency guarantee: a second generation call
    for the same period cannot create a duplicate work item. ``work_item_id``
    records which WorkItem was produced.
    """

    recurring_profile_id = models.UUIDField(db_index=True)
    period_key = models.CharField(max_length=20, db_index=True)
    work_item_id = models.UUIDField(db_index=True)
    generated_on = models.DateField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["tenant_id", "recurring_profile_id", "period_key"],
                name="uq_generated_profile_period",
            )
        ]
        ordering = ["-created_at"]
