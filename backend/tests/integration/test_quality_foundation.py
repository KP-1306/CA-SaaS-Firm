from __future__ import annotations

import uuid

import pytest
from django.db import IntegrityError
from django.test import Client as HttpClient

from contexts.quality.models import (
    QAChecklistStatus,
    QAReviewCycle,
    QAReviewCycleStatus,
    ServiceQAChecklistItem,
    ServiceQAChecklistSet,
)

TENANT_A = uuid.UUID("11111111-1111-1111-1111-111111111111")
TENANT_B = uuid.UUID("33333333-3333-3333-3333-333333333333")
PRINCIPAL = uuid.UUID("22222222-2222-2222-2222-222222222222")


def _headers(tenant=TENANT_A, principal=PRINCIPAL):
    return {
        "HTTP_X_TENANT_ID": str(tenant),
        "HTTP_X_PRINCIPAL_ID": str(principal),
    }


@pytest.mark.django_db
def test_quality_models_store_versioned_service_checklist():
    service_id = uuid.uuid4()
    checklist = ServiceQAChecklistSet.objects.create(
        tenant_id=TENANT_A,
        created_by=PRINCIPAL,
        updated_by=PRINCIPAL,
        service_id=service_id,
        name="GST Return QA",
        version_number=1,
        status=QAChecklistStatus.ACTIVE,
    )
    item = ServiceQAChecklistItem.objects.create(
        tenant_id=TENANT_A,
        created_by=PRINCIPAL,
        updated_by=PRINCIPAL,
        checklist_set_id=checklist.id,
        service_id=service_id,
        code="GST-001",
        title="Verify outward supplies",
    )
    assert item.checklist_set_id == checklist.id


@pytest.mark.django_db
def test_quality_cycle_is_tenant_scoped_and_versioned():
    work_item_id = uuid.uuid4()
    first = QAReviewCycle.objects.create(
        tenant_id=TENANT_A,
        created_by=PRINCIPAL,
        updated_by=PRINCIPAL,
        work_item_id=work_item_id,
        cycle_number=1,
        status=QAReviewCycleStatus.PREPARATION,
    )
    second = QAReviewCycle.objects.create(
        tenant_id=TENANT_B,
        created_by=PRINCIPAL,
        updated_by=PRINCIPAL,
        work_item_id=work_item_id,
        cycle_number=1,
        status=QAReviewCycleStatus.PREPARATION,
    )
    assert first.tenant_id != second.tenant_id


@pytest.mark.django_db(transaction=True)
def test_quality_cycle_number_is_unique_per_tenant_work():
    work_item_id = uuid.uuid4()
    QAReviewCycle.objects.create(
        tenant_id=TENANT_A,
        created_by=PRINCIPAL,
        updated_by=PRINCIPAL,
        work_item_id=work_item_id,
        cycle_number=1,
    )
    with pytest.raises(IntegrityError):
        QAReviewCycle.objects.create(
            tenant_id=TENANT_A,
            created_by=PRINCIPAL,
            updated_by=PRINCIPAL,
            work_item_id=work_item_id,
            cycle_number=1,
        )


@pytest.mark.django_db
def test_quality_checklist_api_is_tenant_scoped():
    http = HttpClient()
    service_id = uuid.uuid4()
    created = http.post(
        "/api/v1/service-qa-checklist-sets/",
        data={
            "service_id": str(service_id),
            "name": "Income Tax Return QA",
            "version_number": 1,
            "status": "ACTIVE",
        },
        content_type="application/json",
        **_headers(),
    )
    assert created.status_code == 201, created.content
    assert created.json()["tenant_id"] == str(TENANT_A)

    tenant_b = http.get(
        "/api/v1/service-qa-checklist-sets/",
        **_headers(tenant=TENANT_B),
    )
    assert tenant_b.status_code == 200
    assert tenant_b.json() in ([], {"count": 0, "results": []})
