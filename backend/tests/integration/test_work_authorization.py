from __future__ import annotations

import pytest
from django.test import Client as HttpClient

from contexts.authorization.models import (
    Access,
    AccessProfile,
    RoleAccess,
    RoleTemplate,
)
from contexts.clients.models import Client
from contexts.identity.models import ProviderRole
from contexts.work.models import WorkItem
from tests.integration.test_vridhi_consultant_admin import (
    ADMIN_PRINCIPAL,
    OTHER_PRINCIPAL,
    TENANT,
    _identity,
    _login,
)


pytestmark = pytest.mark.django_db


def _grant(account, *codes: str) -> AccessProfile:
    role = RoleTemplate.objects.create(
        tenant_id=TENANT,
        code=f"WORK_{account.id.hex[:10].upper()}",
        name="Test Work Role",
        is_system=False,
        is_active=True,
    )

    for code in codes:
        access, _ = Access.objects.get_or_create(
            code=code,
            defaults={
                "module": "Workflow",
                "name": code,
                "is_active": True,
            },
        )

        RoleAccess.objects.create(
            role=role,
            access=access,
        )

    return AccessProfile.objects.create(
        tenant_id=TENANT,
        user_account_id=account.id,
        role=role,
        is_active=True,
    )


def _client() -> Client:
    return Client.objects.create(
        tenant_id=TENANT,
        created_by=ADMIN_PRINCIPAL,
        updated_by=ADMIN_PRINCIPAL,
        legal_name="Authorization Client",
        client_type="INDIVIDUAL",
    )


def _work_item(*, owner_id=None, reviewer_id=None) -> WorkItem:
    return WorkItem.objects.create(
        tenant_id=TENANT,
        created_by=ADMIN_PRINCIPAL,
        updated_by=ADMIN_PRINCIPAL,
        title="Authorization Work",
        client_id=_client().id,
        owner_user_id=owner_id,
        reviewer_user_id=reviewer_id,
    )


def test_user_with_work_view_can_list_work_items():
    account, _, _ = _identity(
        email="work-viewer@vridhi.example",
        principal=OTHER_PRINCIPAL,
        role=ProviderRole.IMPLEMENTATION_CONSULTANT,
    )
    _grant(account, "work.view")

    http = HttpClient()
    _login(http, account)

    response = http.get("/api/v1/work-items/")

    assert response.status_code == 200, response.content


def test_user_without_work_view_is_denied():
    account, _, _ = _identity(
        email="work-denied@vridhi.example",
        principal=OTHER_PRINCIPAL,
        role=ProviderRole.IMPLEMENTATION_CONSULTANT,
    )

    http = HttpClient()
    _login(http, account)

    response = http.get("/api/v1/work-items/")

    assert response.status_code == 403
    assert "work.view" in response.content.decode()


def test_work_view_does_not_allow_work_creation():
    account, _, _ = _identity(
        email="work-readonly@vridhi.example",
        principal=OTHER_PRINCIPAL,
        role=ProviderRole.IMPLEMENTATION_CONSULTANT,
    )
    _grant(account, "work.view")

    http = HttpClient()
    _login(http, account)

    response = http.post(
        "/api/v1/work-items/",
        data={
            "title": "Denied Work",
            "client_id": str(_client().id),
        },
        content_type="application/json",
    )

    assert response.status_code == 403
    assert "work.create" in response.content.decode()


def test_work_create_allows_creation():
    account, _, _ = _identity(
        email="work-creator@vridhi.example",
        principal=ADMIN_PRINCIPAL,
        role=ProviderRole.OPERATIONS_ADMIN,
    )
    _grant(
        account,
        "work.view",
        "work.create",
    )

    http = HttpClient()
    _login(http, account)

    response = http.post(
        "/api/v1/work-items/",
        data={
            "title": "Authorized Work",
            "client_id": str(_client().id),
        },
        content_type="application/json",
    )

    assert response.status_code == 201, response.content
    assert response.json()["title"] == "Authorized Work"


def test_submit_capability_is_required_before_owner_guard():
    account, _, employee = _identity(
        email="work-owner@vridhi.example",
        principal=OTHER_PRINCIPAL,
        role=ProviderRole.IMPLEMENTATION_CONSULTANT,
    )
    _grant(account, "work.view")

    item = _work_item(owner_id=employee.id)

    http = HttpClient()
    _login(http, account)

    response = http.post(
        f"/api/v1/work-items/{item.id}/set_status/",
        data={"status": "IN_PROGRESS"},
        content_type="application/json",
    )

    assert response.status_code == 403
    assert "work.submit" in response.content.decode()


def test_submit_capability_preserves_existing_owner_workflow_guard():
    account, _, employee = _identity(
        email="work-submitter@vridhi.example",
        principal=OTHER_PRINCIPAL,
        role=ProviderRole.IMPLEMENTATION_CONSULTANT,
    )
    _grant(
        account,
        "work.view",
        "work.submit",
    )

    item = _work_item(owner_id=employee.id)

    http = HttpClient()
    _login(http, account)

    response = http.post(
        f"/api/v1/work-items/{item.id}/set_status/",
        data={"status": "IN_PROGRESS"},
        content_type="application/json",
    )

    assert response.status_code == 200, response.content
    assert response.json()["status"] == "IN_PROGRESS"


def test_assignment_capability_is_separate_from_work_submission():
    account, _, employee = _identity(
        email="work-assignment-denied@vridhi.example",
        principal=ADMIN_PRINCIPAL,
        role=ProviderRole.OPERATIONS_ADMIN,
    )
    _grant(
        account,
        "work.view",
        "work.submit",
    )

    item = _work_item(owner_id=employee.id)

    http = HttpClient()
    _login(http, account)

    response = http.post(
        f"/api/v1/work-items/{item.id}/assign/",
        data={"owner_user_id": str(employee.id)},
        content_type="application/json",
    )

    assert response.status_code == 403
    assert "work.assign" in response.content.decode()


def test_approval_capability_is_separate_from_submit_capability():
    account, _, employee = _identity(
        email="work-approval-denied@vridhi.example",
        principal=OTHER_PRINCIPAL,
        role=ProviderRole.IMPLEMENTATION_CONSULTANT,
    )
    _grant(
        account,
        "work.view",
        "work.submit",
    )

    item = _work_item(reviewer_id=employee.id)

    http = HttpClient()
    _login(http, account)

    response = http.post(
        f"/api/v1/work-items/{item.id}/approve/",
        data={},
        content_type="application/json",
    )

    assert response.status_code == 403
    assert "work.approve" in response.content.decode()


def test_legacy_header_workflow_compatibility_remains_test_only():
    response = HttpClient().get(
        "/api/v1/work-items/",
        HTTP_X_TENANT_ID=str(TENANT),
        HTTP_X_PRINCIPAL_ID=str(OTHER_PRINCIPAL),
    )

    assert response.status_code == 200
