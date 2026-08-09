from __future__ import annotations

import datetime as dt
import uuid

import pytest

from contexts.configuration.models import (
    ServiceOperationalField,
)
from contexts.generation.generation import (
    generate_for_profile,
)
from contexts.generation.models import (
    ClientServiceSubscription,
    RecurringWorkProfile,
)
from contexts.generation.serializers import (
    RecurringWorkProfileSerializer,
)
from contexts.work.models import WorkItem


TENANT = uuid.UUID(
    "11111111-1111-1111-1111-111111111111"
)
PRINCIPAL = uuid.UUID(
    "22222222-2222-2222-2222-222222222222"
)
CLIENT = uuid.UUID(
    "33333333-3333-3333-3333-333333333333"
)
SERVICE = uuid.UUID(
    "44444444-4444-4444-4444-444444444444"
)


class _Principal:
    tenant_id = TENANT


class _Request:
    principal = _Principal()
    META = {}


def _subscription():
    return ClientServiceSubscription.objects.create(
        tenant_id=TENANT,
        created_by=PRINCIPAL,
        updated_by=PRINCIPAL,
        client_id=CLIENT,
        service_id=SERVICE,
        frequency="QUARTERLY",
        status="ACTIVE",
    )


def _field(
    *,
    key="tds_form",
    label="TDS Form",
    field_type="SELECT",
    required=True,
    options=None,
):
    return ServiceOperationalField.objects.create(
        tenant_id=TENANT,
        created_by=PRINCIPAL,
        updated_by=PRINCIPAL,
        service_id=SERVICE,
        key=key,
        label=label,
        field_type=field_type,
        required=required,
        options=(
            options
            if options is not None
            else ["24Q", "26Q", "27Q", "27EQ"]
        ),
        display_order=10,
        is_active=True,
    )


@pytest.mark.django_db
def test_profile_rejects_subscription_client_mismatch():
    subscription = _subscription()
    _field()

    serializer = RecurringWorkProfileSerializer(
        data={
            "subscription_id": str(subscription.id),
            "client_id": str(uuid.uuid4()),
            "service_id": str(SERVICE),
            "frequency": "QUARTERLY",
            "operational_defaults": {
                "tds_form": "26Q",
            },
        },
        context={"request": _Request()},
    )

    assert not serializer.is_valid()
    assert "client_id" in serializer.errors


@pytest.mark.django_db
def test_profile_rejects_subscription_service_mismatch():
    subscription = _subscription()
    _field()

    serializer = RecurringWorkProfileSerializer(
        data={
            "subscription_id": str(subscription.id),
            "client_id": str(CLIENT),
            "service_id": str(uuid.uuid4()),
            "frequency": "QUARTERLY",
            "operational_defaults": {},
        },
        context={"request": _Request()},
    )

    assert not serializer.is_valid()
    assert "service_id" in serializer.errors


@pytest.mark.django_db
def test_profile_rejects_invalid_select_default():
    subscription = _subscription()
    _field()

    serializer = RecurringWorkProfileSerializer(
        data={
            "subscription_id": str(subscription.id),
            "client_id": str(CLIENT),
            "service_id": str(SERVICE),
            "frequency": "QUARTERLY",
            "operational_defaults": {
                "tds_form": "INVALID",
            },
        },
        context={"request": _Request()},
    )

    assert not serializer.is_valid()
    assert "operational_defaults" in serializer.errors


@pytest.mark.django_db
def test_profile_rejects_unknown_operational_default():
    subscription = _subscription()
    _field()

    serializer = RecurringWorkProfileSerializer(
        data={
            "subscription_id": str(subscription.id),
            "client_id": str(CLIENT),
            "service_id": str(SERVICE),
            "frequency": "QUARTERLY",
            "operational_defaults": {
                "unknown_field": "x",
            },
        },
        context={"request": _Request()},
    )

    assert not serializer.is_valid()
    assert "operational_defaults" in serializer.errors


@pytest.mark.django_db
def test_profile_defaults_are_allowed_to_be_partial():
    subscription = _subscription()

    _field(
        key="tds_form",
        label="TDS Form",
        required=True,
    )

    _field(
        key="financial_year",
        label="Financial Year",
        field_type="TEXT",
        required=True,
        options=[],
    )

    _field(
        key="quarter",
        label="Quarter",
        field_type="SELECT",
        required=True,
        options=["Q1", "Q2", "Q3", "Q4"],
    )

    serializer = RecurringWorkProfileSerializer(
        data={
            "subscription_id": str(subscription.id),
            "client_id": str(CLIENT),
            "service_id": str(SERVICE),
            "frequency": "QUARTERLY",
            "operational_defaults": {
                "tds_form": "26Q",
            },
        },
        context={"request": _Request()},
    )

    assert serializer.is_valid(), serializer.errors

    assert serializer.validated_data[
        "operational_defaults"
    ] == {
        "tds_form": "26Q",
    }


@pytest.mark.django_db
def test_profile_default_propagates_to_generated_work():
    subscription = _subscription()
    _field()

    profile = RecurringWorkProfile.objects.create(
        tenant_id=TENANT,
        created_by=PRINCIPAL,
        updated_by=PRINCIPAL,
        subscription_id=subscription.id,
        client_id=CLIENT,
        service_id=SERVICE,
        frequency="QUARTERLY",
        operational_defaults={
            "tds_form": "26Q",
        },
    )

    result = generate_for_profile(
        profile,
        on_date=dt.date(2026, 7, 1),
        principal_id=PRINCIPAL,
    )

    assert result.created is True

    item = WorkItem.objects.get(
        tenant_id=TENANT,
        id=result.work_item_id,
    )

    assert item.operational_data == {
        "tds_form": "26Q",
    }


@pytest.mark.django_db
def test_two_profiles_under_one_subscription_are_isolated():
    subscription = _subscription()
    _field()

    profile_24q = RecurringWorkProfile.objects.create(
        tenant_id=TENANT,
        created_by=PRINCIPAL,
        updated_by=PRINCIPAL,
        subscription_id=subscription.id,
        client_id=CLIENT,
        service_id=SERVICE,
        frequency="QUARTERLY",
        operational_defaults={
            "tds_form": "24Q",
        },
    )

    profile_26q = RecurringWorkProfile.objects.create(
        tenant_id=TENANT,
        created_by=PRINCIPAL,
        updated_by=PRINCIPAL,
        subscription_id=subscription.id,
        client_id=CLIENT,
        service_id=SERVICE,
        frequency="QUARTERLY",
        operational_defaults={
            "tds_form": "26Q",
        },
    )

    one = generate_for_profile(
        profile_24q,
        on_date=dt.date(2026, 7, 1),
        principal_id=PRINCIPAL,
    )

    two = generate_for_profile(
        profile_26q,
        on_date=dt.date(2026, 7, 1),
        principal_id=PRINCIPAL,
    )

    first = WorkItem.objects.get(
        tenant_id=TENANT,
        id=one.work_item_id,
    )

    second = WorkItem.objects.get(
        tenant_id=TENANT,
        id=two.work_item_id,
    )

    assert first.id != second.id
    assert first.operational_data == {
        "tds_form": "24Q",
    }
    assert second.operational_data == {
        "tds_form": "26Q",
    }
