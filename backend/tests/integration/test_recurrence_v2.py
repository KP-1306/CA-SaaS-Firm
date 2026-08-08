import datetime as dt
import uuid

import pytest

TENANT = uuid.UUID(
    "11111111-1111-1111-1111-111111111111"
)
PRINCIPAL = uuid.UUID(
    "22222222-2222-2222-2222-222222222222"
)


def make_subscription(**overrides):
    from contexts.generation.models import (
        ClientServiceSubscription,
    )

    values = {
        "tenant_id": TENANT,
        "created_by": PRINCIPAL,
        "updated_by": PRINCIPAL,
        "client_id": uuid.uuid4(),
        "service_id": uuid.uuid4(),
        "frequency": "MONTHLY",
        "status": "ACTIVE",
    }
    values.update(overrides)

    return ClientServiceSubscription.objects.create(
        **values
    )


def make_template(service_id, **overrides):
    from contexts.generation.models import TaskTemplate

    values = {
        "tenant_id": TENANT,
        "created_by": PRINCIPAL,
        "updated_by": PRINCIPAL,
        "service_id": service_id,
        "name": "GST Monthly Return",
        "default_title": "GST Return",
        "default_priority": "HIGH",
        "default_due_days": 10,
        "default_estimated_hours": "4.50",
        "is_active": True,
    }
    values.update(overrides)

    return TaskTemplate.objects.create(**values)


def make_profile(subscription, template=None, **overrides):
    from contexts.generation.models import (
        RecurringWorkProfile,
    )

    values = {
        "tenant_id": TENANT,
        "created_by": PRINCIPAL,
        "updated_by": PRINCIPAL,
        "subscription_id": subscription.id,
        "task_template_id": (
            template.id if template else None
        ),
        "client_id": subscription.client_id,
        "service_id": subscription.service_id,
        "frequency": "MONTHLY",
        "is_active": True,
    }
    values.update(overrides)

    return RecurringWorkProfile.objects.create(
        **values
    )


@pytest.mark.django_db
def test_preview_does_not_create_work():
    from contexts.generation.generation import (
        preview_for_profile,
    )
    from contexts.work.models import WorkItem

    subscription = make_subscription()
    template = make_template(
        subscription.service_id
    )
    profile = make_profile(
        subscription,
        template,
    )

    preview = preview_for_profile(
        profile,
        on_date=dt.date(2026, 8, 1),
    )

    assert preview.eligible is True
    assert preview.already_generated is False
    assert preview.period_key == "2026-08"
    assert preview.title == "GST Return"
    assert preview.due_date == "2026-08-11"
    assert preview.priority == "HIGH"
    assert preview.estimated_hours == "4.50"
    assert WorkItem.objects.filter(
        tenant_id=TENANT
    ).count() == 0


@pytest.mark.django_db
def test_generation_inherits_template_defaults():
    from contexts.generation.generation import (
        generate_for_profile,
    )
    from contexts.work.models import WorkItem

    subscription = make_subscription()
    template = make_template(
        subscription.service_id
    )
    profile = make_profile(
        subscription,
        template,
    )

    result = generate_for_profile(
        profile,
        on_date=dt.date(2026, 8, 1),
        principal_id=PRINCIPAL,
    )

    item = WorkItem.objects.get(
        id=result.work_item_id
    )

    assert item.title == "GST Return"
    assert item.priority == "HIGH"
    assert item.due_date == dt.date(
        2026,
        8,
        11,
    )
    assert str(item.estimated_hours) == "4.50"


@pytest.mark.django_db
def test_paused_subscription_is_blocked():
    from contexts.generation.generation import (
        preview_for_profile,
    )

    subscription = make_subscription(
        status="PAUSED"
    )
    profile = make_profile(subscription)

    preview = preview_for_profile(
        profile,
        on_date=dt.date(2026, 8, 1),
    )

    assert preview.eligible is False
    assert (
        "not active"
        in preview.reason.lower()
    )


@pytest.mark.django_db
def test_inactive_profile_is_blocked():
    from contexts.generation.generation import (
        preview_for_profile,
    )

    subscription = make_subscription()
    profile = make_profile(
        subscription,
        is_active=False,
    )

    preview = preview_for_profile(
        profile,
        on_date=dt.date(2026, 8, 1),
    )

    assert preview.eligible is False
    assert "inactive" in preview.reason.lower()


@pytest.mark.django_db
def test_existing_period_appears_as_duplicate():
    from contexts.generation.generation import (
        generate_for_profile,
        preview_for_profile,
    )

    subscription = make_subscription()
    profile = make_profile(subscription)

    generate_for_profile(
        profile,
        on_date=dt.date(2026, 8, 1),
        principal_id=PRINCIPAL,
    )

    preview = preview_for_profile(
        profile,
        on_date=dt.date(2026, 8, 20),
    )

    assert preview.eligible is False
    assert preview.already_generated is True
    assert preview.work_item_id is not None
