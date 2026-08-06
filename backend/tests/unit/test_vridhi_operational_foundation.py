
from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest
from django.db import IntegrityError
from django.db import transaction

from contexts.configuration.models import (
    ServiceOperationalField,
)
from contexts.configuration.serializers import (
    ServiceOperationalFieldSerializer,
)
from contexts.work.models import WorkItem
from contexts.work.serializers import WorkItemSerializer


pytestmark = pytest.mark.django_db


def _request(tenant_id, principal_id=None):
    return SimpleNamespace(
        user=SimpleNamespace(
            tenant_id=tenant_id,
            principal_id=principal_id or uuid4(),
        )
    )


def _field(
    *,
    tenant_id,
    service_id,
    key,
    label,
    field_type="TEXT",
    options=None,
    required=False,
):
    actor_id = uuid4()

    return ServiceOperationalField.objects.create(
        tenant_id=tenant_id,
        created_by=actor_id,
        updated_by=actor_id,
        service_id=service_id,
        key=key,
        label=label,
        field_type=field_type,
        options=options or [],
        required=required,
    )


def test_service_operational_field_is_tenant_and_service_scoped():
    tenant_id = uuid4()
    service_id = uuid4()

    first = _field(
        tenant_id=tenant_id,
        service_id=service_id,
        key="loan_amount",
        label="Loan Amount",
        field_type="NUMBER",
    )

    assert first.key == "loan_amount"

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            _field(
                tenant_id=tenant_id,
                service_id=service_id,
                key="loan_amount",
                label="Requested Loan Amount",
                field_type="NUMBER",
            )


def test_same_field_key_is_allowed_for_another_service():
    tenant_id = uuid4()

    first = _field(
        tenant_id=tenant_id,
        service_id=uuid4(),
        key="loan_amount",
        label="Loan Amount",
        field_type="NUMBER",
    )

    second = _field(
        tenant_id=tenant_id,
        service_id=uuid4(),
        key="loan_amount",
        label="Loan Amount",
        field_type="NUMBER",
    )

    assert first.service_id != second.service_id


def test_select_field_requires_options():
    tenant_id = uuid4()

    serializer = ServiceOperationalFieldSerializer(
        data={
            "service_id": str(uuid4()),
            "key": "applicant_type",
            "label": "Applicant Type",
            "field_type": "SELECT",
            "options": [],
        },
        context={"request": _request(tenant_id)},
    )

    assert not serializer.is_valid()
    assert "options" in serializer.errors


def test_select_field_cleans_duplicate_and_blank_options():
    tenant_id = uuid4()

    serializer = ServiceOperationalFieldSerializer(
        data={
            "service_id": str(uuid4()),
            "key": "applicant_type",
            "label": "Applicant Type",
            "field_type": "SELECT",
            "options": [
                "Salaried",
                " ",
                "Salaried",
                "Self-employed",
            ],
        },
        context={"request": _request(tenant_id)},
    )

    assert serializer.is_valid(), serializer.errors
    assert serializer.validated_data["options"] == [
        "Salaried",
        "Self-employed",
    ]


def test_work_item_operational_data_is_validated_by_service_fields():
    tenant_id = uuid4()
    service_id = uuid4()

    _field(
        tenant_id=tenant_id,
        service_id=service_id,
        key="applicant_type",
        label="Applicant Type",
        field_type="SELECT",
        options=["Salaried", "Self-employed"],
        required=True,
    )

    _field(
        tenant_id=tenant_id,
        service_id=service_id,
        key="loan_amount",
        label="Loan Amount",
        field_type="NUMBER",
        required=True,
    )

    serializer = WorkItemSerializer(
        data={
            "title": "Home Loan Application",
            "client_id": str(uuid4()),
            "service_id": str(service_id),
            "operational_data": {
                "applicant_type": "Salaried",
                "loan_amount": "4500000",
            },
        },
        context={"request": _request(tenant_id)},
    )

    assert serializer.is_valid(), serializer.errors
    assert serializer.validated_data["operational_data"] == {
        "applicant_type": "Salaried",
        "loan_amount": 4500000.0,
    }


def test_required_operational_field_is_enforced():
    tenant_id = uuid4()
    service_id = uuid4()

    _field(
        tenant_id=tenant_id,
        service_id=service_id,
        key="loan_amount",
        label="Loan Amount",
        field_type="NUMBER",
        required=True,
    )

    serializer = WorkItemSerializer(
        data={
            "title": "Loan Application",
            "client_id": str(uuid4()),
            "service_id": str(service_id),
            "operational_data": {},
        },
        context={"request": _request(tenant_id)},
    )

    assert not serializer.is_valid()
    assert "operational_data" in serializer.errors


def test_unknown_operational_field_is_rejected():
    tenant_id = uuid4()
    service_id = uuid4()

    _field(
        tenant_id=tenant_id,
        service_id=service_id,
        key="loan_amount",
        label="Loan Amount",
        field_type="NUMBER",
    )

    serializer = WorkItemSerializer(
        data={
            "title": "Loan Application",
            "client_id": str(uuid4()),
            "service_id": str(service_id),
            "operational_data": {
                "unapproved_field": "value",
            },
        },
        context={"request": _request(tenant_id)},
    )

    assert not serializer.is_valid()
    assert "operational_data" in serializer.errors


def test_operational_values_without_service_are_rejected():
    tenant_id = uuid4()

    serializer = WorkItemSerializer(
        data={
            "title": "Unclassified Work",
            "client_id": str(uuid4()),
            "operational_data": {
                "loan_amount": 100000,
            },
        },
        context={"request": _request(tenant_id)},
    )

    assert not serializer.is_valid()
    assert "operational_data" in serializer.errors


def test_existing_work_items_default_to_empty_operational_data():
    item = WorkItem(
        tenant_id=uuid4(),
        title="Existing Work",
        client_id=uuid4(),
    )

    assert item.operational_data == {}
