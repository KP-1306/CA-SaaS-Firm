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
    MembershipStatus,
    ProviderMembership,
    ProviderRole,
    UserAccount,
    UserAccountStatus,
)

TENANT = uuid.UUID("11111111-1111-1111-1111-111111111111")
PRINCIPAL = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")


def _account(*, email="consultant@vridhi.example", status=UserAccountStatus.ACTIVE):
    account = UserAccount(email=email, display_name="Vridhi Consultant", status=status)
    account.set_password("Strong-Test-Password-123!")
    account.email_verified_at = timezone.now()
    account.save()
    membership = ProviderMembership.objects.create(
        tenant_id=TENANT,
        created_by=PRINCIPAL,
        updated_by=PRINCIPAL,
        user_account_id=account.id,
        employee_id=PRINCIPAL,
        role=ProviderRole.IMPLEMENTATION_CONSULTANT,
        status=MembershipStatus.ACTIVE,
    )
    return account, membership


@pytest.mark.django_db
def test_vridhi_consultant_login_me_and_logout():
    account, _ = _account()
    http = HttpClient(enforce_csrf_checks=True)
    csrf = http.get("/api/v1/auth/login/").json()["csrf_token"]
    login = http.post(
        "/api/v1/auth/login/",
        data={"email": account.email.upper(), "password": "Strong-Test-Password-123!"},
        content_type="application/json",
        HTTP_X_CSRFTOKEN=csrf,
    )
    assert login.status_code == 200, login.content
    assert login.json()["membership"]["role"] == ProviderRole.IMPLEMENTATION_CONSULTANT
    assert "vridhi_session" in login.cookies
    me = http.get("/api/v1/auth/me/")
    assert me.status_code == 200, me.content
    assert me.json()["account"]["email"] == account.email
    csrf = http.cookies["csrftoken"].value
    logout = http.post(
        "/api/v1/auth/logout/",
        data={},
        content_type="application/json",
        HTTP_X_CSRFTOKEN=csrf,
    )
    assert logout.status_code == 204
    assert AuthSession.objects.get().revoked_at is not None
    assert AuthenticationEvent.objects.filter(
        event_type=AuthenticationEventType.LOGIN_SUCCEEDED
    ).exists()
    assert AuthenticationEvent.objects.filter(
        event_type=AuthenticationEventType.LOGOUT
    ).exists()


@pytest.mark.django_db
def test_invalid_password_is_audited_and_does_not_create_session():
    account, _ = _account()
    response = HttpClient().post(
        "/api/v1/auth/login/",
        data={"email": account.email, "password": "wrong"},
        content_type="application/json",
    )
    assert response.status_code == 403
    account.refresh_from_db()
    assert account.failed_login_count == 1
    assert not AuthSession.objects.exists()
    assert AuthenticationEvent.objects.filter(
        event_type=AuthenticationEventType.LOGIN_FAILED,
        reason="INVALID_CREDENTIALS",
    ).exists()


@pytest.mark.django_db
def test_suspended_account_and_membership_are_denied():
    account, membership = _account(status=UserAccountStatus.SUSPENDED)
    response = HttpClient().post(
        "/api/v1/auth/login/",
        data={"email": account.email, "password": "Strong-Test-Password-123!"},
        content_type="application/json",
    )
    assert response.status_code == 403
    account.status = UserAccountStatus.ACTIVE
    account.save(update_fields=["status", "updated_at"])
    membership.status = MembershipStatus.SUSPENDED
    membership.save(update_fields=["status", "updated_at"])
    response = HttpClient().post(
        "/api/v1/auth/login/",
        data={"email": account.email, "password": "Strong-Test-Password-123!"},
        content_type="application/json",
    )
    assert response.status_code == 403


@pytest.mark.django_db
def test_expired_session_cannot_authenticate():
    account, membership = _account()
    AuthSession.objects.create(
        user_account_id=account.id,
        membership_id=membership.id,
        tenant_id=TENANT,
        principal_id=PRINCIPAL,
        token_hash=AuthSession.digest("expired-token"),
        expires_at=timezone.now() - timedelta(seconds=1),
    )
    http = HttpClient()
    http.cookies["vridhi_session"] = "expired-token"
    response = http.get("/api/v1/auth/me/")
    assert response.status_code == 403


@pytest.mark.django_db
def test_session_principal_can_access_existing_tenant_api():
    account, _ = _account()
    http = HttpClient()
    login = http.post(
        "/api/v1/auth/login/",
        data={"email": account.email, "password": "Strong-Test-Password-123!"},
        content_type="application/json",
    )
    assert login.status_code == 200
    response = http.get("/api/v1/employees/")
    assert response.status_code == 200, response.content


@pytest.mark.django_db
def test_header_principal_compatibility_remains_test_only():
    response = HttpClient().get(
        "/api/v1/employees/",
        HTTP_X_TENANT_ID=str(TENANT),
        HTTP_X_PRINCIPAL_ID=str(PRINCIPAL),
    )
    assert response.status_code == 200


@pytest.mark.django_db
def test_authentication_event_is_append_only():
    event = AuthenticationEvent.objects.create(
        event_type=AuthenticationEventType.LOGIN_FAILED,
        outcome="FAILURE",
        email="unknown@example.com",
    )
    event.reason = "changed"
    with pytest.raises(RuntimeError, match="append-only"):
        event.save()
    with pytest.raises(RuntimeError, match="append-only"):
        event.delete()
