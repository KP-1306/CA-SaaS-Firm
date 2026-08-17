from __future__ import annotations

import uuid

import pytest
from django.test import Client as HttpClient
from django.utils import timezone

from contexts.clients.models import ClientContact
from contexts.configuration.models import (
    Service,
    ServiceDocumentRequirement,
    ServiceDocumentRequirementSet,
)
from contexts.work.models import (
    DocumentRequest,
    DocumentRequestStatus,
)


TENANT = "11111111-1111-1111-1111-111111111111"
OWNER = "22222222-2222-2222-2222-222222222222"


def _headers():
    return {
        "HTTP_X_TENANT_ID": TENANT,
        "HTTP_X_PRINCIPAL_ID": OWNER,
    }


def _create_client(http: HttpClient) -> str:
    response = http.post(
        "/api/v1/clients/",
        data={
            "legal_name": "Phase 3C Client",
            "client_type": "PRIVATE_LIMITED",
            "pan": "ABCDE1234F",
        },
        content_type="application/json",
        **_headers(),
    )

    assert response.status_code == 201, response.content

    return response.json()["id"]


def _create_contact(client_id: str) -> ClientContact:
    return ClientContact.objects.create(
        tenant_id=TENANT,
        created_by=OWNER,
        updated_by=OWNER,
        client_id=client_id,
        name="Phase 3C Client POC",
        email="phase3c-poc@example.com",
        is_active=True,
        can_receive_document_requests=True,
    )


def _create_service(
    *,
    code: str = "PHASE3C_HOME_LOAN",
    name: str = "Phase 3C Home Loan",
) -> Service:
    return Service.objects.create(
        tenant_id=TENANT,
        created_by=OWNER,
        updated_by=OWNER,
        domain_id=uuid.uuid4(),
        name=name,
        code=code,
        description="Phase 3C certification service.",
        status="ACTIVE",
    )


def _create_requirement_set(
    service: Service,
    *,
    version: int = 1,
    status: str = "ACTIVE",
    effective_from=None,
    effective_until=None,
) -> ServiceDocumentRequirementSet:
    return ServiceDocumentRequirementSet.objects.create(
        tenant_id=TENANT,
        created_by=OWNER,
        updated_by=OWNER,
        service_id=service.id,
        name=f"{service.name} Checklist V{version}",
        version_number=version,
        effective_from=effective_from,
        effective_until=effective_until,
        status=status,
        description="Phase 3C certification checklist.",
    )


def _create_requirement(
    service: Service,
    requirement_set: ServiceDocumentRequirementSet,
    *,
    code: str,
    name: str,
    mandatory: bool = True,
    display_order: int = 10,
    category: str = "OTHER",
) -> ServiceDocumentRequirement:
    return ServiceDocumentRequirement.objects.create(
        tenant_id=TENANT,
        created_by=OWNER,
        updated_by=OWNER,
        requirement_set_id=requirement_set.id,
        service_id=service.id,
        code=code,
        name=name,
        description=f"Provide {name}.",
        category=category,
        mandatory=mandatory,
        display_order=display_order,
        is_active=True,
    )


def _create_work(
    http: HttpClient,
    *,
    client_id: str,
    service_id: str,
):
    response = http.post(
        "/api/v1/work-items/",
        data={
            "title": "Home Loan Processing",
            "client_id": client_id,
            "service_id": service_id,
            "owner_user_id": OWNER,
            "priority": "NORMAL",
        },
        content_type="application/json",
        **_headers(),
    )

    assert response.status_code == 201, response.content

    return response.json()


@pytest.mark.django_db
def test_work_creation_materializes_active_service_checklist():
    http = HttpClient()

    client_id = _create_client(http)
    contact = _create_contact(client_id)

    service = _create_service()
    requirement_set = _create_requirement_set(service)

    pan = _create_requirement(
        service,
        requirement_set,
        code="PAN",
        name="PAN Card",
        mandatory=True,
        display_order=10,
        category="IDENTITY_KYC",
    )

    bank = _create_requirement(
        service,
        requirement_set,
        code="BANK_STATEMENT",
        name="Bank Statement",
        mandatory=False,
        display_order=20,
        category="BANKING",
    )

    work = _create_work(
        http,
        client_id=client_id,
        service_id=str(service.id),
    )

    requests = list(
        DocumentRequest.objects.filter(
            tenant_id=TENANT,
            work_item_id=work["id"],
        ).order_by("name")
    )

    assert len(requests) == 2

    by_source = {
        str(row.source_requirement_id): row
        for row in requests
    }

    assert str(pan.id) in by_source
    assert str(bank.id) in by_source

    pan_request = by_source[str(pan.id)]
    bank_request = by_source[str(bank.id)]

    assert pan_request.name == "PAN Card"
    assert pan_request.mandatory is True
    assert pan_request.category == "IDENTITY_KYC"

    assert bank_request.name == "Bank Statement"
    assert bank_request.mandatory is False
    assert bank_request.category == "BANKING"

    for row in requests:
        assert row.auto_generated is True
        assert row.status == DocumentRequestStatus.REQUESTED
        assert str(row.source_requirement_set_id) == str(
            requirement_set.id
        )
        assert str(row.requested_from_contact_id) == str(contact.id)
        assert str(row.client_id) == str(client_id)


@pytest.mark.django_db
def test_only_latest_effective_active_requirement_set_is_used():
    http = HttpClient()

    client_id = _create_client(http)
    _create_contact(client_id)

    service = _create_service(
        code="PHASE3C_VERSIONING",
        name="Phase 3C Versioning",
    )

    old_set = _create_requirement_set(
        service,
        version=1,
        status="ACTIVE",
        effective_from=timezone.now().date(),
    )

    old_requirement = _create_requirement(
        service,
        old_set,
        code="OLD_DOC",
        name="Old Document",
    )

    new_set = _create_requirement_set(
        service,
        version=2,
        status="ACTIVE",
        effective_from=timezone.now().date(),
    )

    new_requirement = _create_requirement(
        service,
        new_set,
        code="NEW_DOC",
        name="New Document",
    )

    work = _create_work(
        http,
        client_id=client_id,
        service_id=str(service.id),
    )

    requests = DocumentRequest.objects.filter(
        tenant_id=TENANT,
        work_item_id=work["id"],
    )

    assert requests.count() == 1

    request = requests.get()

    assert str(request.source_requirement_id) == str(
        new_requirement.id
    )

    assert str(request.source_requirement_set_id) == str(
        new_set.id
    )

    assert not requests.filter(
        source_requirement_id=old_requirement.id
    ).exists()


@pytest.mark.django_db
def test_inactive_requirements_are_not_materialized():
    http = HttpClient()

    client_id = _create_client(http)
    _create_contact(client_id)

    service = _create_service(
        code="PHASE3C_INACTIVE_REQ",
        name="Phase 3C Inactive Requirement",
    )

    requirement_set = _create_requirement_set(service)

    active_requirement = _create_requirement(
        service,
        requirement_set,
        code="ACTIVE_DOC",
        name="Active Document",
    )

    inactive_requirement = _create_requirement(
        service,
        requirement_set,
        code="INACTIVE_DOC",
        name="Inactive Document",
    )

    inactive_requirement.is_active = False
    inactive_requirement.save(
        update_fields=["is_active"]
    )

    work = _create_work(
        http,
        client_id=client_id,
        service_id=str(service.id),
    )

    requests = DocumentRequest.objects.filter(
        tenant_id=TENANT,
        work_item_id=work["id"],
    )

    assert requests.count() == 1
    assert requests.filter(
        source_requirement_id=active_requirement.id
    ).exists()

    assert not requests.filter(
        source_requirement_id=inactive_requirement.id
    ).exists()


@pytest.mark.django_db
def test_generation_is_idempotent_and_does_not_duplicate_requests():
    http = HttpClient()

    client_id = _create_client(http)
    _create_contact(client_id)

    service = _create_service(
        code="PHASE3C_IDEMPOTENT",
        name="Phase 3C Idempotent",
    )

    requirement_set = _create_requirement_set(service)

    requirement = _create_requirement(
        service,
        requirement_set,
        code="PAN",
        name="PAN Card",
    )

    work = _create_work(
        http,
        client_id=client_id,
        service_id=str(service.id),
    )

    initial = DocumentRequest.objects.filter(
        tenant_id=TENANT,
        work_item_id=work["id"],
        source_requirement_id=requirement.id,
    )

    assert initial.count() == 1

    response = http.post(
        (
            f"/api/v1/work-items/{work['id']}/"
            "generate-document-requests/"
        ),
        data={},
        content_type="application/json",
        **_headers(),
    )

    assert response.status_code == 200, response.content

    assert response.json()["created"] == 0
    assert response.json()["existing"] == 1

    assert DocumentRequest.objects.filter(
        tenant_id=TENANT,
        work_item_id=work["id"],
        source_requirement_id=requirement.id,
    ).count() == 1


@pytest.mark.django_db
def test_no_active_requirement_set_does_not_break_work_creation():
    http = HttpClient()

    client_id = _create_client(http)
    _create_contact(client_id)

    service = _create_service(
        code="PHASE3C_NO_SET",
        name="Phase 3C No Requirement Set",
    )

    work = _create_work(
        http,
        client_id=client_id,
        service_id=str(service.id),
    )

    assert work["id"]

    assert not DocumentRequest.objects.filter(
        tenant_id=TENANT,
        work_item_id=work["id"],
    ).exists()


@pytest.mark.django_db
def test_missing_eligible_contact_does_not_break_work_creation():
    http = HttpClient()

    client_id = _create_client(http)

    service = _create_service(
        code="PHASE3C_NO_CONTACT",
        name="Phase 3C No Contact",
    )

    requirement_set = _create_requirement_set(service)

    _create_requirement(
        service,
        requirement_set,
        code="PAN",
        name="PAN Card",
    )

    work = _create_work(
        http,
        client_id=client_id,
        service_id=str(service.id),
    )

    assert work["id"]

    request = DocumentRequest.objects.get(
        tenant_id=TENANT,
        work_item_id=work["id"],
    )

    assert request.requested_from_contact_id is None
    assert request.sent_at is None


@pytest.mark.django_db
def test_requirement_from_other_service_is_never_materialized():
    http = HttpClient()

    client_id = _create_client(http)
    _create_contact(client_id)

    selected_service = _create_service(
        code="PHASE3C_SELECTED",
        name="Selected Service",
    )

    selected_set = _create_requirement_set(
        selected_service
    )

    selected_requirement = _create_requirement(
        selected_service,
        selected_set,
        code="SELECTED_DOC",
        name="Selected Document",
    )

    other_service = _create_service(
        code="PHASE3C_OTHER",
        name="Other Service",
    )

    other_set = _create_requirement_set(
        other_service
    )

    other_requirement = _create_requirement(
        other_service,
        other_set,
        code="OTHER_DOC",
        name="Other Document",
    )

    work = _create_work(
        http,
        client_id=client_id,
        service_id=str(selected_service.id),
    )

    requests = DocumentRequest.objects.filter(
        tenant_id=TENANT,
        work_item_id=work["id"],
    )

    assert requests.filter(
        source_requirement_id=selected_requirement.id
    ).exists()

    assert not requests.filter(
        source_requirement_id=other_requirement.id
    ).exists()
