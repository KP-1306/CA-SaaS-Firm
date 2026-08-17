
from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest
from rest_framework.test import APIRequestFactory
from django.db import IntegrityError
from django.db import transaction

from contexts.configuration.models import (
    ServiceOperationalField,
    ServiceProcessStep,
)
from contexts.configuration.views import (
    ServiceOperationalFieldViewSet,
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


def test_operational_field_api_accepts_boolean_query_strings():
    tenant_id = uuid4()
    service_id = uuid4()
    principal_id = uuid4()

    _field(
        tenant_id=tenant_id,
        service_id=service_id,
        key="required_field",
        label="Required Field",
        required=True,
    )

    _field(
        tenant_id=tenant_id,
        service_id=service_id,
        key="optional_field",
        label="Optional Field",
        required=False,
    )

    from django.test import Client as HttpClient

    http = HttpClient()

    response = http.get(
        "/api/v1/service-operational-fields/",
        {
            "service_id": str(service_id),
            "required": "true",
            "is_active": "true",
        },
        HTTP_X_TENANT_ID=str(tenant_id),
        HTTP_X_PRINCIPAL_ID=str(principal_id),
    )

    assert response.status_code == 200, response.content

    payload = response.json()

    rows = (
        payload.get("results", payload)
        if isinstance(payload, dict)
        else payload
    )

    assert len(rows) == 1
    assert rows[0]["key"] == "required_field"
    assert rows[0]["required"] is True

    response = http.get(
        "/api/v1/service-operational-fields/",
        {
            "service_id": str(service_id),
            "required": "false",
            "is_active": "true",
        },
        HTTP_X_TENANT_ID=str(tenant_id),
        HTTP_X_PRINCIPAL_ID=str(principal_id),
    )

    assert response.status_code == 200, response.content

    payload = response.json()

    rows = (
        payload.get("results", payload)
        if isinstance(payload, dict)
        else payload
    )

    assert len(rows) == 1
    assert rows[0]["key"] == "optional_field"
    assert rows[0]["required"] is False


def test_service_process_step_api_filters_by_service_and_active_state():
    from django.test import Client as HttpClient

    tenant_id = uuid4()
    other_tenant_id = uuid4()
    principal_id = uuid4()

    service_id = uuid4()
    other_service_id = uuid4()

    common = {
        "created_by": principal_id,
        "updated_by": principal_id,
    }

    ServiceProcessStep.objects.create(
        tenant_id=tenant_id,
        service_id=service_id,
        code="VERIFY",
        name="Verification",
        display_order=20,
        is_active=True,
        **common,
    )

    ServiceProcessStep.objects.create(
        tenant_id=tenant_id,
        service_id=service_id,
        code="CLIENT_INFORMATION",
        name="Client Information",
        display_order=10,
        is_active=True,
        **common,
    )

    ServiceProcessStep.objects.create(
        tenant_id=tenant_id,
        service_id=service_id,
        code="OLD_STEP",
        name="Old Step",
        display_order=5,
        is_active=False,
        **common,
    )

    ServiceProcessStep.objects.create(
        tenant_id=tenant_id,
        service_id=other_service_id,
        code="OTHER_SERVICE",
        name="Other Service Step",
        display_order=1,
        is_active=True,
        **common,
    )

    ServiceProcessStep.objects.create(
        tenant_id=other_tenant_id,
        service_id=service_id,
        code="OTHER_TENANT",
        name="Other Tenant Step",
        display_order=1,
        is_active=True,
        **common,
    )

    http = HttpClient()

    response = http.get(
        "/api/v1/service-process-steps/",
        {
            "service_id": str(service_id),
            "is_active": "true",
        },
        HTTP_X_TENANT_ID=str(tenant_id),
        HTTP_X_PRINCIPAL_ID=str(principal_id),
    )

    assert response.status_code == 200, response.content

    payload = response.json()

    rows = (
        payload.get("results", payload)
        if isinstance(payload, dict)
        else payload
    )

    assert [
        row["code"]
        for row in rows
    ] == [
        "CLIENT_INFORMATION",
        "VERIFY",
    ]

    assert all(
        row["service_id"] == str(service_id)
        for row in rows
    )

    assert all(
        row["is_active"] is True
        for row in rows
    )

    assert "OTHER_TENANT" not in {
        row["code"]
        for row in rows
    }


def test_service_process_step_unique_code_is_scoped_to_tenant_and_service():
    from django.db import IntegrityError, transaction

    tenant_id = uuid4()
    principal_id = uuid4()
    service_id = uuid4()

    common = {
        "created_by": principal_id,
        "updated_by": principal_id,
    }

    ServiceProcessStep.objects.create(
        tenant_id=tenant_id,
        service_id=service_id,
        code="VERIFY",
        name="Verification",
        display_order=10,
        **common,
    )

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            ServiceProcessStep.objects.create(
                tenant_id=tenant_id,
                service_id=service_id,
                code="VERIFY",
                name="Duplicate Verification",
                display_order=20,
                **common,
            )

    # Same code under another service is valid.
    ServiceProcessStep.objects.create(
        tenant_id=tenant_id,
        service_id=uuid4(),
        code="VERIFY",
        name="Verification",
        display_order=10,
        **common,
    )

    # Same code under another tenant is also valid.
    ServiceProcessStep.objects.create(
        tenant_id=uuid4(),
        service_id=service_id,
        code="VERIFY",
        name="Verification",
        display_order=10,
        **common,
    )


def test_service_process_step_serializer_exposes_definition_fields():
    from contexts.configuration.serializers import (
        ServiceProcessStepSerializer,
    )

    tenant_id = uuid4()
    principal_id = uuid4()
    service_id = uuid4()

    row = ServiceProcessStep.objects.create(
        tenant_id=tenant_id,
        service_id=service_id,
        code="APPLICATION_SUBMISSION",
        name="Application Submission",
        description="Submit the prepared application.",
        display_order=40,
        is_active=True,
        created_by=principal_id,
        updated_by=principal_id,
    )

    data = ServiceProcessStepSerializer(row).data

    assert data["service_id"] == str(service_id)
    assert data["code"] == "APPLICATION_SUBMISSION"
    assert data["name"] == "Application Submission"
    assert data["display_order"] == 40
    assert data["is_active"] is True
