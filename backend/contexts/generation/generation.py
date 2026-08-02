"""Deterministic, idempotent work generation for recurring profiles.

This is a FOUNDATION, not a scheduler. It exposes pure helpers plus one atomic
generator that creates at most one WorkItem per (profile, period) and records it
in ``GeneratedWorkLedger``. Re-invoking for the same period is a no-op (the
ledger's unique constraint makes it idempotent even under a race).

No background jobs, no billing, no external effects. All references are UUIDs;
all writes are tenant-scoped and carry the audit columns.
"""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass

from django.db import IntegrityError, transaction

from contexts.work.models import WorkItem, WorkStatus
from .models import GeneratedWorkLedger, RecurrenceFrequency


def period_key_for(frequency: str, on_date: _dt.date) -> str:
    """Return a stable period key for a date under a recurrence frequency.

    Deterministic and dependency-free so tests can assert exact keys:
      MONTHLY      -> "YYYY-MM"
      QUARTERLY    -> "YYYY-Q{1..4}"
      HALF_YEARLY  -> "YYYY-H{1,2}"
      YEARLY       -> "YYYY"
      NONE/other   -> "YYYY-MM-DD" (a single concrete day; still idempotent)
    """
    y = on_date.year
    m = on_date.month
    if frequency == RecurrenceFrequency.MONTHLY:
        return f"{y:04d}-{m:02d}"
    if frequency == RecurrenceFrequency.QUARTERLY:
        return f"{y:04d}-Q{((m - 1) // 3) + 1}"
    if frequency == RecurrenceFrequency.HALF_YEARLY:
        return f"{y:04d}-H{1 if m <= 6 else 2}"
    if frequency == RecurrenceFrequency.YEARLY:
        return f"{y:04d}"
    return on_date.isoformat()


@dataclass
class GenerationResult:
    """Outcome of a single generation attempt."""

    created: bool
    period_key: str
    work_item_id: object | None
    already_generated: bool


def _due_date_for(profile, on_date: _dt.date) -> _dt.date | None:
    default_due_days = getattr(profile, "default_due_days", None)
    if default_due_days:
        return on_date + _dt.timedelta(days=int(default_due_days))
    return None


@transaction.atomic
def generate_for_profile(
    profile,
    *,
    on_date: _dt.date,
    principal_id,
    title: str | None = None,
) -> GenerationResult:
    """Create at most one WorkItem for ``profile`` in the period of ``on_date``.

    Idempotent: if a ledger row already exists for (profile, period_key), no new
    work item is created. The WorkItem and ledger row are created together in one
    atomic transaction; a unique-violation race collapses to "already generated".
    """
    period_key = period_key_for(profile.frequency, on_date)

    existing = GeneratedWorkLedger.objects.filter(
        tenant_id=profile.tenant_id,
        recurring_profile_id=profile.id,
        period_key=period_key,
    ).first()
    if existing is not None:
        return GenerationResult(
            created=False,
            period_key=period_key,
            work_item_id=existing.work_item_id,
            already_generated=True,
        )

    resolved_title = title or f"Recurring work {period_key}"
    try:
        with transaction.atomic():
            work_item = WorkItem.objects.create(
                tenant_id=profile.tenant_id,
                created_by=principal_id,
                updated_by=principal_id,
                title=resolved_title,
                client_id=profile.client_id,
                service_id=profile.service_id,
                owner_user_id=profile.default_owner_user_id,
                reviewer_user_id=profile.default_reviewer_user_id,
                period=period_key,
                due_date=_due_date_for(profile, on_date),
                status=WorkStatus.NOT_STARTED,
            )
            ledger = GeneratedWorkLedger.objects.create(
                tenant_id=profile.tenant_id,
                created_by=principal_id,
                updated_by=principal_id,
                recurring_profile_id=profile.id,
                period_key=period_key,
                work_item_id=work_item.id,
                generated_on=on_date,
            )
    except IntegrityError:
        # A concurrent call won the unique (profile, period_key) race. Idempotent
        # outcome: report the already-generated row.
        existing = GeneratedWorkLedger.objects.filter(
            tenant_id=profile.tenant_id,
            recurring_profile_id=profile.id,
            period_key=period_key,
        ).first()
        return GenerationResult(
            created=False,
            period_key=period_key,
            work_item_id=existing.work_item_id if existing else None,
            already_generated=True,
        )

    return GenerationResult(
        created=True,
        period_key=period_key,
        work_item_id=ledger.work_item_id,
        already_generated=False,
    )
