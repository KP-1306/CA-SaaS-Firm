from __future__ import annotations

import uuid
from datetime import timedelta

import pytest
from django.test import Client as HttpClient
from django.utils import timezone

from contexts.identity.models import (
    AuthenticationEvent,
    AuthenticationEventType,
    AuthSession,
    Employee,
    FirmRole,
    MembershipStatus,
    ProviderMembership,
    ProviderRole,
    UserAccount,
    UserAccountStatus,
)

TENANT = uuid.UUID("11111111-1111-1111-1111-111111111111")
ADMIN_PRINCIPAL = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
OTHER_PRINCIPAL = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")


def _identity(
    *,
    email: str,
    principal: uuid.UUID,
    role: str,
):
    employee = Employee.objects.create(
        tenant_id=TENANT,
        created_by=principal,
        updated_by=principal,
        name=email.split("@")[0],
        email=email,
        role=FirmRole.ADMIN,
        principal_id=principal,
        is_active=True,
    )
    account = UserAccount(
        email=email,
        display_name=employee.name,
        status=UserAccountStatus.ACTIVE,
    )
    account.set_password("Strong-Test-Password-123!")
    account.email_verified_at = timezone.now()
    account.save()
    membership = ProviderMembership.objects.create(
        tenant_id=TENANT,
        created_by=principal,
        updated_by=principal,
        user_account_id=account.id,
        employee_id=employee.id,
        role=role,
        status=MembershipStatus.ACTIVE,
    )
    return account, membership, employee


def _login(http, account):
    response = http.post(
        "/api/v1/auth/login/",
        data={
            "email": account.email,
            "password": "Strong-Test-Password-123!",
        },
        content_type="application/json",
    )
    assert response.status_code == 200, response.content


@pytest.mark.django_db
def test_platform_admin_can_create_and_list_consultants():
    admin, _, _ = _identity(
        email="admin@vridhi.example",
        principal=ADMIN_PRINCIPAL,
        role=ProviderRole.PLATFORM_ADMIN,
    )
    http = HttpClient()
    _login(http, admin)

    response = http.post(
        "/api/v1/identity/consultants/",
        data={
            "email": "new.consultant@vridhi.example",
            "display_name": "New Consultant",
            "role": ProviderRole.IMPLEMENTATION_CONSULTANT,
        },
        content_type="application/json",
    )
    assert response.status_code == 201, response.content
    body = response.json()
    assert body["temporary_password_disclosed_once"] is True
    assert body["consultant"]["must_change_password"] is True
    assert UserAccount.objects.filter(
        email="new.consultant@vridhi.example"
    ).exists()

    listed = http.get("/api/v1/identity/consultants/")
    assert listed.status_code == 200
    assert len(listed.json()) == 2


@pytest.mark.django_db
def test_non_admin_cannot_access_consultant_administration():
    consultant, _, _ = _identity(
        email="consultant@vridhi.example",
        principal=OTHER_PRINCIPAL,
        role=ProviderRole.IMPLEMENTATION_CONSULTANT,
    )
    http = HttpClient()
    _login(http, consultant)
    response = http.get("/api/v1/identity/consultants/")
    assert response.status_code == 403
    assert AuthenticationEvent.objects.filter(
        event_type=AuthenticationEventType.ACCESS_DENIED,
        reason="CONSULTANT_ADMIN_REQUIRED",
    ).exists()


@pytest.mark.django_db
def test_admin_can_change_role_and_suspend_with_session_revocation():
    admin, _, _ = _identity(
        email="admin@vridhi.example",
        principal=ADMIN_PRINCIPAL,
        role=ProviderRole.PLATFORM_ADMIN,
    )
    target, target_membership, _ = _identity(
        email="target@vridhi.example",
        principal=OTHER_PRINCIPAL,
        role=ProviderRole.SUPPORT_CONSULTANT,
    )

    target_session = AuthSession.objects.create(
        user_account_id=target.id,
        membership_id=target_membership.id,
        tenant_id=TENANT,
        principal_id=OTHER_PRINCIPAL,
        token_hash=AuthSession.digest("target-token"),
        expires_at=timezone.now() + timedelta(hours=1),
    )

    http = HttpClient()
    _login(http, admin)

    role_response = http.post(
        f"/api/v1/identity/consultants/{target.id}/role/",
        data={
            "role": ProviderRole.SECURITY_AUDITOR,
            "reason": "Assigned audit responsibility",
        },
        content_type="application/json",
    )
    assert role_response.status_code == 200, role_response.content
    target_membership.refresh_from_db()
    assert target_membership.role == ProviderRole.SECURITY_AUDITOR

    suspend = http.post(
        f"/api/v1/identity/consultants/{target.id}/status/",
        data={
            "status": UserAccountStatus.SUSPENDED,
            "reason": "Temporary security hold",
        },
        content_type="application/json",
    )
    assert suspend.status_code == 200, suspend.content
    target.refresh_from_db()
    target_session.refresh_from_db()
    assert target.status == UserAccountStatus.SUSPENDED
    assert target_session.revoked_at is not None


@pytest.mark.django_db
def test_admin_can_link_employee_reset_password_unlock_and_revoke_sessions():
    admin, _, _ = _identity(
        email="admin@vridhi.example",
        principal=ADMIN_PRINCIPAL,
        role=ProviderRole.OPERATIONS_ADMIN,
    )
    target, target_membership, _ = _identity(
        email="target@vridhi.example",
        principal=OTHER_PRINCIPAL,
        role=ProviderRole.IMPLEMENTATION_CONSULTANT,
    )
    new_employee = Employee.objects.create(
        tenant_id=TENANT,
        created_by=ADMIN_PRINCIPAL,
        updated_by=ADMIN_PRINCIPAL,
        name="Replacement Employee",
        email="replacement@vridhi.example",
        role=FirmRole.STAFF,
        is_active=True,
    )

    target.failed_login_count = 5
    target.locked_until = timezone.now() + timedelta(minutes=10)
    target.save(
        update_fields=["failed_login_count", "locked_until", "updated_at"]
    )

    http = HttpClient()
    _login(http, admin)

    link = http.post(
        f"/api/v1/identity/consultants/{target.id}/employee-link/",
        data={"employee_id": str(new_employee.id)},
        content_type="application/json",
    )
    assert link.status_code == 200, link.content
    target_membership.refresh_from_db()
    assert target_membership.employee_id == new_employee.id

    unlock = http.post(
        f"/api/v1/identity/consultants/{target.id}/unlock/",
        data={},
        content_type="application/json",
    )
    assert unlock.status_code == 200
    target.refresh_from_db()
    assert target.locked_until is None
    assert target.failed_login_count == 0

    reset = http.post(
        f"/api/v1/identity/consultants/{target.id}/password-reset/",
        data={},
        content_type="application/json",
    )
    assert reset.status_code == 200
    assert reset.json()["temporary_password_disclosed_once"] is True
    target.refresh_from_db()
    assert target.must_change_password is True

    sessions = http.get(
        f"/api/v1/identity/consultants/{target.id}/sessions/"
    )
    assert sessions.status_code == 200

    revoked = http.delete(
        f"/api/v1/identity/consultants/{target.id}/sessions/"
    )
    assert revoked.status_code == 200


@pytest.mark.django_db
def test_consultant_auth_audit_is_visible_to_admin():
    admin, _, _ = _identity(
        email="admin@vridhi.example",
        principal=ADMIN_PRINCIPAL,
        role=ProviderRole.PLATFORM_ADMIN,
    )
    target, target_membership, _ = _identity(
        email="target@vridhi.example",
        principal=OTHER_PRINCIPAL,
        role=ProviderRole.SUPPORT_CONSULTANT,
    )
    AuthenticationEvent.objects.create(
        tenant_id=TENANT,
        user_account_id=target.id,
        principal_id=OTHER_PRINCIPAL,
        event_type=AuthenticationEventType.LOGIN_FAILED,
        outcome="FAILURE",
        email=target.email,
        reason="INVALID_CREDENTIALS",
    )

    http = HttpClient()
    _login(http, admin)
    response = http.get(
        f"/api/v1/identity/consultants/{target.id}/audit/"
    )
    assert response.status_code == 200
    assert any(
        row["event_type"] == AuthenticationEventType.LOGIN_FAILED
        for row in response.json()
    )
