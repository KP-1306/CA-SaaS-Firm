"""Recurrence foundation tests (V1 additive, ctx_generation).

Covers the deterministic period-key function (pure, no DB) and the idempotent
generator (DB-backed): a second generation for the same period creates no
duplicate work item.
"""

from __future__ import annotations

import datetime as dt
import uuid

import pytest

TENANT_A = "11111111-1111-1111-1111-111111111111"
PRINCIPAL = "22222222-2222-2222-2222-222222222222"


def test_period_key_is_deterministic():
    from contexts.generation.generation import period_key_for

    d = dt.date(2026, 5, 17)
    assert period_key_for("MONTHLY", d) == "2026-05"
    assert period_key_for("QUARTERLY", d) == "2026-Q2"
    assert period_key_for("HALF_YEARLY", d) == "2026-H1"
    assert period_key_for("YEARLY", d) == "2026"
    assert period_key_for("NONE", d) == "2026-05-17"
    # Quarter boundaries
    assert period_key_for("QUARTERLY", dt.date(2026, 1, 1)) == "2026-Q1"
    assert period_key_for("QUARTERLY", dt.date(2026, 12, 31)) == "2026-Q4"
    assert period_key_for("HALF_YEARLY", dt.date(2026, 7, 1)) == "2026-H2"


def _make_profile():
    from contexts.generation.models import RecurringWorkProfile

    return RecurringWorkProfile.objects.create(
        tenant_id=TENANT_A,
        created_by=PRINCIPAL,
        updated_by=PRINCIPAL,
        subscription_id=uuid.uuid4(),
        client_id=uuid.uuid4(),
        service_id=uuid.uuid4(),
        frequency="MONTHLY",
    )


@pytest.mark.django_db
def test_generation_is_idempotent_per_period():
    from contexts.generation.generation import generate_for_profile
    from contexts.generation.models import GeneratedWorkLedger
    from contexts.work.models import WorkItem

    profile = _make_profile()
    on_date = dt.date(2026, 5, 10)

    first = generate_for_profile(profile, on_date=on_date, principal_id=PRINCIPAL)
    assert first.created is True
    assert first.period_key == "2026-05"

    # Same period again -> no new work item, reports already generated.
    second = generate_for_profile(profile, on_date=dt.date(2026, 5, 28), principal_id=PRINCIPAL)
    assert second.created is False
    assert second.already_generated is True
    assert second.work_item_id == first.work_item_id

    assert GeneratedWorkLedger.objects.filter(
        tenant_id=TENANT_A, recurring_profile_id=profile.id
    ).count() == 1
    assert WorkItem.objects.filter(tenant_id=TENANT_A, period="2026-05").count() == 1


@pytest.mark.django_db
def test_generation_creates_new_item_next_period():
    from contexts.generation.generation import generate_for_profile

    profile = _make_profile()
    a = generate_for_profile(profile, on_date=dt.date(2026, 5, 10), principal_id=PRINCIPAL)
    b = generate_for_profile(profile, on_date=dt.date(2026, 6, 10), principal_id=PRINCIPAL)
    assert a.created and b.created
    assert a.work_item_id != b.work_item_id
    assert a.period_key == "2026-05" and b.period_key == "2026-06"


@pytest.mark.django_db
def test_generated_work_item_is_not_started_and_linked():
    from contexts.generation.generation import generate_for_profile
    from contexts.work.models import WorkItem, WorkStatus

    profile = _make_profile()
    result = generate_for_profile(profile, on_date=dt.date(2026, 5, 10), principal_id=PRINCIPAL)
    item = WorkItem.objects.get(tenant_id=TENANT_A, id=result.work_item_id)
    assert item.status == WorkStatus.NOT_STARTED
    assert item.client_id == profile.client_id
    assert item.service_id == profile.service_id
