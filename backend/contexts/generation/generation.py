"""Deterministic, idempotent recurring-work generation.

The engine remains explicitly invoked: there is no scheduler and no unattended
generation.  It supports preview -> human approval -> generation while keeping
the existing GeneratedWorkLedger as the duplicate/idempotency authority.
"""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass
from decimal import Decimal

from django.db import IntegrityError, transaction

from contexts.configuration.deadline_rules import calculate_compliance_due_date

from contexts.work.models import WorkItem, WorkStatus

from .models import (
    ClientServiceSubscription,
    GeneratedWorkLedger,
    RecurrenceFrequency,
    SubscriptionStatus,
    TaskTemplate,
)


def period_key_for(
    frequency: str,
    on_date: _dt.date,
) -> str:
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
    created: bool
    period_key: str
    work_item_id: object | None
    already_generated: bool


@dataclass
class GenerationPreview:
    profile_id: str
    period_key: str
    eligible: bool
    already_generated: bool
    reason: str
    work_item_id: str | None
    client_id: str
    service_id: str
    title: str
    due_date: str | None
    owner_user_id: str | None
    reviewer_user_id: str | None
    priority: str
    estimated_hours: str | None


def _template_for(profile):
    template_id = getattr(
        profile,
        "task_template_id",
        None,
    )

    if not template_id:
        return None

    return TaskTemplate.objects.filter(
        tenant_id=profile.tenant_id,
        id=template_id,
        is_active=True,
    ).first()


def _subscription_for(profile):
    return ClientServiceSubscription.objects.filter(
        tenant_id=profile.tenant_id,
        id=profile.subscription_id,
    ).first()


def _resolved_values(
    profile,
    *,
    on_date: _dt.date,
    title: str | None = None,
) -> dict:
    template = _template_for(profile)
    subscription = _subscription_for(profile)

    resolved_title = (
        title
        or (
            template.default_title
            if template and template.default_title
            else ""
        )
        or (
            template.name
            if template
            else ""
        )
        or f"Recurring work {period_key_for(profile.frequency, on_date)}"
    )

    operational_context = dict(
        getattr(
            profile,
            "operational_defaults",
            None,
        )
        or {}
    )

    due_date = calculate_compliance_due_date(
        tenant_id=profile.tenant_id,
        service_id=profile.service_id,
        frequency=profile.frequency,
        on_date=on_date,
        operational_context=operational_context,
    )

    if (
        due_date is None
        and template
        and template.default_due_days is not None
    ):
        due_date = on_date + _dt.timedelta(
            days=int(template.default_due_days),
        )

    owner_user_id = (
        profile.default_owner_user_id
        or (
            template.default_owner_user_id
            if template
            else None
        )
        or (
            subscription.default_owner_user_id
            if subscription
            else None
        )
    )

    reviewer_user_id = (
        profile.default_reviewer_user_id
        or (
            template.default_reviewer_user_id
            if template
            else None
        )
        or (
            subscription.default_reviewer_user_id
            if subscription
            else None
        )
    )

    priority = (
        template.default_priority
        if template and template.default_priority
        else "NORMAL"
    )

    estimated_hours: Decimal | None = (
        template.default_estimated_hours
        if template
        else None
    )

    description = (
        template.description
        if template
        else ""
    )

    return {
        "template": template,
        "subscription": subscription,
        "title": resolved_title,
        "description": description,
        "due_date": due_date,
        "owner_user_id": owner_user_id,
        "reviewer_user_id": reviewer_user_id,
        "priority": priority,
        "estimated_hours": estimated_hours,
        "operational_data": dict(
            operational_context
        ),
    }


def _eligibility(
    profile,
    *,
    on_date: _dt.date,
) -> tuple[bool, str]:
    if not profile.is_active:
        return False, "Recurring profile is inactive."

    subscription = _subscription_for(profile)

    if subscription is None:
        return False, "Client service subscription was not found."

    if subscription.status != SubscriptionStatus.ACTIVE:
        return (
            False,
            "Client service subscription is not active.",
        )

    if (
        subscription.start_date
        and on_date < subscription.start_date
    ):
        return (
            False,
            "Subscription has not started yet.",
        )

    if (
        subscription.end_date
        and on_date > subscription.end_date
    ):
        return (
            False,
            "Subscription has ended.",
        )

    if profile.frequency == RecurrenceFrequency.NONE:
        return (
            False,
            "Recurring profile frequency is NONE.",
        )

    return True, ""


def preview_for_profile(
    profile,
    *,
    on_date: _dt.date,
    title: str | None = None,
) -> GenerationPreview:
    period_key = period_key_for(
        profile.frequency,
        on_date,
    )

    existing = GeneratedWorkLedger.objects.filter(
        tenant_id=profile.tenant_id,
        recurring_profile_id=profile.id,
        period_key=period_key,
    ).first()

    resolved = _resolved_values(
        profile,
        on_date=on_date,
        title=title,
    )

    eligible, reason = _eligibility(
        profile,
        on_date=on_date,
    )

    if existing is not None:
        eligible = False
        reason = "Work has already been generated for this period."

    return GenerationPreview(
        profile_id=str(profile.id),
        period_key=period_key,
        eligible=eligible,
        already_generated=existing is not None,
        reason=reason,
        work_item_id=(
            str(existing.work_item_id)
            if existing
            else None
        ),
        client_id=str(profile.client_id),
        service_id=str(profile.service_id),
        title=resolved["title"],
        due_date=(
            resolved["due_date"].isoformat()
            if resolved["due_date"]
            else None
        ),
        owner_user_id=(
            str(resolved["owner_user_id"])
            if resolved["owner_user_id"]
            else None
        ),
        reviewer_user_id=(
            str(resolved["reviewer_user_id"])
            if resolved["reviewer_user_id"]
            else None
        ),
        priority=resolved["priority"],
        estimated_hours=(
            str(resolved["estimated_hours"])
            if resolved["estimated_hours"] is not None
            else None
        ),
    )


@transaction.atomic
def generate_for_profile(
    profile,
    *,
    on_date: _dt.date,
    principal_id,
    title: str | None = None,
    enforce_eligibility: bool = False,
) -> GenerationResult:
    preview = preview_for_profile(
        profile,
        on_date=on_date,
        title=title,
    )

    if preview.already_generated:
        existing = GeneratedWorkLedger.objects.filter(
            tenant_id=profile.tenant_id,
            recurring_profile_id=profile.id,
            period_key=preview.period_key,
        ).first()

        return GenerationResult(
            created=False,
            period_key=preview.period_key,
            work_item_id=(
                existing.work_item_id
                if existing
                else None
            ),
            already_generated=True,
        )

    if enforce_eligibility and not preview.eligible:
        raise ValueError(preview.reason)

    resolved = _resolved_values(
        profile,
        on_date=on_date,
        title=title,
    )

    try:
        with transaction.atomic():
            work_item = WorkItem.objects.create(
                tenant_id=profile.tenant_id,
                created_by=principal_id,
                updated_by=principal_id,
                title=resolved["title"],
                description=resolved["description"],
                client_id=profile.client_id,
                service_id=profile.service_id,
                owner_user_id=resolved["owner_user_id"],
                reviewer_user_id=resolved["reviewer_user_id"],
                period=preview.period_key,
                due_date=resolved["due_date"],
                status=WorkStatus.NOT_STARTED,
                priority=resolved["priority"],
                estimated_hours=resolved[
                    "estimated_hours"
                ],
                operational_data=dict(
                    resolved["operational_data"]
                ),
            )

            ledger = GeneratedWorkLedger.objects.create(
                tenant_id=profile.tenant_id,
                created_by=principal_id,
                updated_by=principal_id,
                recurring_profile_id=profile.id,
                period_key=preview.period_key,
                work_item_id=work_item.id,
                generated_on=on_date,
            )

    except IntegrityError:
        existing = GeneratedWorkLedger.objects.filter(
            tenant_id=profile.tenant_id,
            recurring_profile_id=profile.id,
            period_key=preview.period_key,
        ).first()

        return GenerationResult(
            created=False,
            period_key=preview.period_key,
            work_item_id=(
                existing.work_item_id
                if existing
                else None
            ),
            already_generated=True,
        )

    return GenerationResult(
        created=True,
        period_key=preview.period_key,
        work_item_id=ledger.work_item_id,
        already_generated=False,
    )
