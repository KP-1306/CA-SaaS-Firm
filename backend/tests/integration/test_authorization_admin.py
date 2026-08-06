from __future__ import annotations

import pytest
from django.test import Client as HttpClient

from contexts.authorization.models import AccessProfile, RoleTemplate
from contexts.identity.models import ProviderRole
from tests.integration.test_vridhi_consultant_admin import (
    ADMIN_PRINCIPAL,
    OTHER_PRINCIPAL,
    TENANT,
    _identity,
    _login,
)


pytestmark = pytest.mark.django_db


def test_admin_can_create_clone_and_update_custom_role():
    admin, _, _ = _identity(
        email="role-admin@vridhi.example",
        principal=ADMIN_PRINCIPAL,
        role=ProviderRole.PLATFORM_ADMIN,
    )

    http = HttpClient()
    _login(http, admin)

    catalogue = http.get("/api/v1/authorization/access/")
    assert catalogue.status_code == 200, catalogue.content
    assert any(
        row["code"] == "clients.view"
        for row in catalogue.json()
    )

    created = http.post(
        "/api/v1/authorization/roles/",
        data={
            "code": "GST_MANAGER",
            "name": "GST Manager",
            "description": "Manages GST work.",
            "access_codes": [
                "clients.view",
                "work.view",
                "work.approve",
            ],
        },
        content_type="application/json",
    )
    assert created.status_code == 201, created.content
    role_id = created.json()["id"]

    cloned = http.post(
        f"/api/v1/authorization/roles/{role_id}/clone/",
        data={
            "code": "GST_REVIEWER",
            "name": "GST Reviewer",
        },
        content_type="application/json",
    )
    assert cloned.status_code == 201, cloned.content

    updated = http.patch(
        f"/api/v1/authorization/roles/{role_id}/",
        data={
            "name": "Senior GST Manager",
            "is_active": False,
        },
        content_type="application/json",
    )
    assert updated.status_code == 200, updated.content
    assert updated.json()["name"] == "Senior GST Manager"
    assert updated.json()["is_active"] is False


def test_system_role_cannot_be_modified():
    admin, _, _ = _identity(
        email="system-role-admin@vridhi.example",
        principal=ADMIN_PRINCIPAL,
        role=ProviderRole.OPERATIONS_ADMIN,
    )

    http = HttpClient()
    _login(http, admin)

    roles = http.get("/api/v1/authorization/roles/")
    assert roles.status_code == 200, roles.content

    partner = next(
        row for row in roles.json()
        if row["code"] == "PARTNER"
    )

    response = http.patch(
        f"/api/v1/authorization/roles/{partner['id']}/",
        data={"name": "Changed Partner"},
        content_type="application/json",
    )

    assert response.status_code == 400
    assert "System roles cannot be modified" in response.content.decode()


def test_admin_can_assign_and_inspect_user_access():
    admin, _, _ = _identity(
        email="access-admin@vridhi.example",
        principal=ADMIN_PRINCIPAL,
        role=ProviderRole.PLATFORM_ADMIN,
    )
    target, _, _ = _identity(
        email="access-target@vridhi.example",
        principal=OTHER_PRINCIPAL,
        role=ProviderRole.IMPLEMENTATION_CONSULTANT,
    )

    http = HttpClient()
    _login(http, admin)

    roles = http.get("/api/v1/authorization/roles/")
    consultant = next(
        row for row in roles.json()
        if row["code"] == "CONSULTANT"
    )

    saved = http.put(
        f"/api/v1/authorization/users/{target.id}/",
        data={
            "role_id": consultant["id"],
            "additional_access_codes": ["reports.export"],
            "department_ids": [],
            "team_ids": [],
            "service_ids": [],
            "is_active": True,
        },
        content_type="application/json",
    )

    assert saved.status_code == 200, saved.content
    payload = saved.json()

    assert payload["role"]["code"] == "CONSULTANT"
    assert "clients.view" in payload["effective_access_codes"]
    assert "reports.export" in payload["effective_access_codes"]

    profile = AccessProfile.objects.get(
        tenant_id=TENANT,
        user_account_id=target.id,
    )
    assert profile.role.code == "CONSULTANT"


def test_non_admin_cannot_manage_authorization():
    user, _, _ = _identity(
        email="non-admin@vridhi.example",
        principal=OTHER_PRINCIPAL,
        role=ProviderRole.IMPLEMENTATION_CONSULTANT,
    )

    http = HttpClient()
    _login(http, user)

    response = http.get("/api/v1/authorization/roles/")
    assert response.status_code == 403
