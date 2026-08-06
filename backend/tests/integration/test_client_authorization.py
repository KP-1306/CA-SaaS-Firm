from __future__ import annotations

import pytest
from django.test import Client as HttpClient

from contexts.authorization.models import (
    Access,
    AccessProfile,
    RoleAccess,
    RoleTemplate,
)
from contexts.identity.models import ProviderRole
from tests.integration.test_vridhi_consultant_admin import (
    ADMIN_PRINCIPAL,
    OTHER_PRINCIPAL,
    TENANT,
    _identity,
    _login,
)


pytestmark = pytest.mark.django_db


def _grant(account, *codes: str):
    role = RoleTemplate.objects.create(
        tenant_id=TENANT,
        code=f"TEST_{account.id.hex[:10].upper()}",
        name="Test Client Role",
        is_system=False,
        is_active=True,
    )

    for code in codes:
        access, _ = Access.objects.get_or_create(
            code=code,
            defaults={
                "module": "Client Management",
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


def test_session_user_with_view_access_can_list_clients():
    account, _, _ = _identity(
        email="client-viewer@vridhi.example",
        principal=OTHER_PRINCIPAL,
        role=ProviderRole.IMPLEMENTATION_CONSULTANT,
    )
    _grant(account, "clients.view")

    http = HttpClient()
    _login(http, account)

    response = http.get("/api/v1/clients/")

    assert response.status_code == 200, response.content


def test_session_user_without_client_access_is_denied():
    account, _, _ = _identity(
        email="client-denied@vridhi.example",
        principal=OTHER_PRINCIPAL,
        role=ProviderRole.IMPLEMENTATION_CONSULTANT,
    )

    http = HttpClient()
    _login(http, account)

    response = http.get("/api/v1/clients/")

    assert response.status_code == 403
    assert "clients.view" in response.content.decode()


def test_view_only_user_cannot_create_client():
    account, _, _ = _identity(
        email="client-readonly@vridhi.example",
        principal=OTHER_PRINCIPAL,
        role=ProviderRole.IMPLEMENTATION_CONSULTANT,
    )
    _grant(account, "clients.view")

    http = HttpClient()
    _login(http, account)

    response = http.post(
        "/api/v1/clients/",
        data={
            "legal_name": "Denied Client",
            "client_type": "INDIVIDUAL",
        },
        content_type="application/json",
    )

    assert response.status_code == 403
    assert "clients.create" in response.content.decode()


def test_create_and_edit_access_follow_separate_capabilities():
    account, _, _ = _identity(
        email="client-editor@vridhi.example",
        principal=ADMIN_PRINCIPAL,
        role=ProviderRole.OPERATIONS_ADMIN,
    )
    _grant(
        account,
        "clients.view",
        "clients.create",
        "clients.edit",
    )

    http = HttpClient()
    _login(http, account)

    created = http.post(
        "/api/v1/clients/",
        data={
            "legal_name": "Authorized Client",
            "client_type": "INDIVIDUAL",
        },
        content_type="application/json",
    )

    assert created.status_code == 201, created.content

    updated = http.patch(
        f"/api/v1/clients/{created.json()['id']}/",
        data={
            "trade_name": "Authorized Trade Name",
        },
        content_type="application/json",
    )

    assert updated.status_code == 200, updated.content
    assert updated.json()["trade_name"] == "Authorized Trade Name"


def test_client_child_endpoints_use_client_capabilities():
    account, _, _ = _identity(
        email="client-contact-admin@vridhi.example",
        principal=ADMIN_PRINCIPAL,
        role=ProviderRole.OPERATIONS_ADMIN,
    )
    _grant(
        account,
        "clients.view",
        "clients.create",
    )

    http = HttpClient()
    _login(http, account)

    client = http.post(
        "/api/v1/clients/",
        data={
            "legal_name": "Contact Parent",
            "client_type": "INDIVIDUAL",
        },
        content_type="application/json",
    )

    assert client.status_code == 201, client.content

    contact = http.post(
        "/api/v1/client-contacts/",
        data={
            "client_id": client.json()["id"],
            "name": "Document Contact",
            "email": "contact@example.com",
        },
        content_type="application/json",
    )

    assert contact.status_code == 201, contact.content

    listing = http.get(
        f"/api/v1/client-contacts/?client_id={client.json()['id']}"
    )

    assert listing.status_code == 200, listing.content
    assert len(listing.json()) == 1


def test_legacy_header_compatibility_remains_test_only():
    response = HttpClient().get(
        "/api/v1/clients/",
        HTTP_X_TENANT_ID=str(TENANT),
        HTTP_X_PRINCIPAL_ID=str(OTHER_PRINCIPAL),
    )

    assert response.status_code == 200
