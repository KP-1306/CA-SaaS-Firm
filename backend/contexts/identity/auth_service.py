from __future__ import annotations

import hashlib
import secrets
from datetime import timedelta
from typing import Any

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework import exceptions
from rest_framework.authentication import BaseAuthentication, CSRFCheck

from core.api.request_context import InternalPrincipal

from .models import (
    AuthenticationEvent,
    AuthenticationEventType,
    AuthenticationOutcome,
    AuthSession,
    MembershipStatus,
    ProviderMembership,
    UserAccount,
    UserAccountStatus,
)

COOKIE_NAME = "vridhi_session"


def _client_ip(request: Any) -> str | None:
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded:
        return forwarded.split(",", 1)[0].strip() or None
    return request.META.get("REMOTE_ADDR")


def _user_agent(request: Any) -> str:
    return str(request.META.get("HTTP_USER_AGENT", ""))[:300]


def record_auth_event(
    *,
    request: Any,
    event_type: str,
    outcome: str,
    email: str = "",
    account: UserAccount | None = None,
    membership: ProviderMembership | None = None,
    session: AuthSession | None = None,
    reason: str = "",
    metadata: dict[str, Any] | None = None,
) -> AuthenticationEvent:
    safe_metadata = {
        str(key): str(value)[:300]
        for key, value in (metadata or {}).items()
        if str(key).lower() not in {"password", "token", "authorization", "cookie"}
    }
    return AuthenticationEvent.objects.create(
        tenant_id=getattr(membership, "tenant_id", None),
        user_account_id=getattr(account, "id", None),
        principal_id=getattr(session, "principal_id", None)
        or getattr(membership, "employee_id", None),
        session_id=getattr(session, "id", None),
        event_type=event_type,
        outcome=outcome,
        email=(email or getattr(account, "email", "") or "").strip().lower(),
        reason=(reason or "")[:200],
        ip_address=_client_ip(request),
        user_agent=_user_agent(request),
        metadata=safe_metadata,
    )


def issue_session(*, request: Any, account: UserAccount, membership: ProviderMembership):
    raw_token = secrets.token_urlsafe(48)
    principal_id = membership.employee_id or account.id
    now = timezone.now()
    session = AuthSession.objects.create(
        user_account_id=account.id,
        membership_id=membership.id,
        tenant_id=membership.tenant_id,
        principal_id=principal_id,
        token_hash=AuthSession.digest(raw_token),
        last_seen_at=now,
        expires_at=now + timedelta(seconds=settings.VRIDHI_SESSION_AGE_SECONDS),
        ip_address=_client_ip(request),
        user_agent_hash=hashlib.sha256(_user_agent(request).encode("utf-8")).hexdigest(),
    )
    record_auth_event(
        request=request,
        event_type=AuthenticationEventType.SESSION_CREATED,
        outcome=AuthenticationOutcome.SUCCESS,
        account=account,
        membership=membership,
        session=session,
    )
    return session, raw_token


def authenticate_credentials(*, request: Any, email: str, password: str):
    normalized = (email or "").strip().lower()
    now = timezone.now()
    account = UserAccount.objects.filter(email=normalized).first()

    if account is None:
        record_auth_event(
            request=request,
            event_type=AuthenticationEventType.LOGIN_FAILED,
            outcome=AuthenticationOutcome.FAILURE,
            email=normalized,
            reason="INVALID_CREDENTIALS",
        )
        raise exceptions.AuthenticationFailed("Invalid email or password.")

    if account.status != UserAccountStatus.ACTIVE:
        record_auth_event(
            request=request,
            event_type=AuthenticationEventType.ACCESS_DENIED,
            outcome=AuthenticationOutcome.DENIED,
            account=account,
            reason=f"ACCOUNT_{account.status}",
        )
        raise exceptions.AuthenticationFailed("This account is not active.")

    if account.locked_until and account.locked_until > now:
        record_auth_event(
            request=request,
            event_type=AuthenticationEventType.LOGIN_FAILED,
            outcome=AuthenticationOutcome.DENIED,
            account=account,
            reason="ACCOUNT_LOCKED",
        )
        raise exceptions.AuthenticationFailed("Account is temporarily locked.")

    if not account.check_password(password):
        account.failed_login_count += 1
        if account.failed_login_count >= settings.VRIDHI_MAX_LOGIN_FAILURES:
            account.locked_until = now + timedelta(seconds=settings.VRIDHI_LOGIN_LOCK_SECONDS)
        account.save(update_fields=["failed_login_count", "locked_until", "updated_at"])
        record_auth_event(
            request=request,
            event_type=AuthenticationEventType.LOGIN_FAILED,
            outcome=AuthenticationOutcome.FAILURE,
            account=account,
            reason="INVALID_CREDENTIALS",
        )
        raise exceptions.AuthenticationFailed("Invalid email or password.")

    membership = ProviderMembership.objects.filter(
        tenant_id=settings.VRIDHI_PROVIDER_TENANT_ID,
        user_account_id=account.id,
        status=MembershipStatus.ACTIVE,
    ).first()
    if membership is None:
        record_auth_event(
            request=request,
            event_type=AuthenticationEventType.ACCESS_DENIED,
            outcome=AuthenticationOutcome.DENIED,
            account=account,
            reason="NO_ACTIVE_PROVIDER_MEMBERSHIP",
        )
        raise exceptions.AuthenticationFailed("No active Vridhi membership.")

    if membership.effective_from > now or (
        membership.effective_to and membership.effective_to <= now
    ):
        record_auth_event(
            request=request,
            event_type=AuthenticationEventType.ACCESS_DENIED,
            outcome=AuthenticationOutcome.DENIED,
            account=account,
            membership=membership,
            reason="MEMBERSHIP_OUTSIDE_EFFECTIVE_PERIOD",
        )
        raise exceptions.AuthenticationFailed("Vridhi membership is not currently valid.")

    with transaction.atomic():
        account.failed_login_count = 0
        account.locked_until = None
        account.last_login_at = now
        account.save(
            update_fields=["failed_login_count", "locked_until", "last_login_at", "updated_at"]
        )
        session, raw_token = issue_session(
            request=request, account=account, membership=membership
        )
        record_auth_event(
            request=request,
            event_type=AuthenticationEventType.LOGIN_SUCCEEDED,
            outcome=AuthenticationOutcome.SUCCESS,
            account=account,
            membership=membership,
            session=session,
        )
    return account, membership, session, raw_token


def revoke_session(*, request: Any, session: AuthSession, reason: str = "LOGOUT") -> None:
    if session.revoked_at is None:
        session.revoked_at = timezone.now()
        session.save(update_fields=["revoked_at"])
    account = UserAccount.objects.filter(id=session.user_account_id).first()
    membership = ProviderMembership.objects.filter(id=session.membership_id).first()
    record_auth_event(
        request=request,
        event_type=(
            AuthenticationEventType.LOGOUT
            if reason == "LOGOUT"
            else AuthenticationEventType.SESSION_REVOKED
        ),
        outcome=AuthenticationOutcome.SUCCESS,
        account=account,
        membership=membership,
        session=session,
        reason=reason,
    )


class VridhiSessionAuthentication(BaseAuthentication):
    def enforce_csrf(self, request: Any) -> None:
        check = CSRFCheck(lambda req: None)
        check.process_request(request)
        reason = check.process_view(request, None, (), {})
        if reason:
            raise exceptions.PermissionDenied(f"CSRF failed: {reason}")

    def authenticate(self, request: Any):
        raw_token = request.COOKIES.get(COOKIE_NAME)
        cookie_used = bool(raw_token)
        if not raw_token:
            authorization = request.headers.get("Authorization", "")
            if authorization.startswith("Bearer "):
                raw_token = authorization[7:].strip()
        if not raw_token:
            return None

        session = AuthSession.objects.filter(
            token_hash=AuthSession.digest(raw_token),
            revoked_at__isnull=True,
            expires_at__gt=timezone.now(),
        ).first()
        if session is None:
            raise exceptions.AuthenticationFailed("Invalid or expired session.")

        account = UserAccount.objects.filter(id=session.user_account_id).first()
        membership = ProviderMembership.objects.filter(id=session.membership_id).first()
        if (
            account is None
            or account.status != UserAccountStatus.ACTIVE
            or membership is None
            or membership.status != MembershipStatus.ACTIVE
            or membership.tenant_id != session.tenant_id
        ):
            raise exceptions.AuthenticationFailed("Account or membership is inactive.")

        if cookie_used and request.method not in {"GET", "HEAD", "OPTIONS", "TRACE"}:
            self.enforce_csrf(request)

        session.last_seen_at = timezone.now()
        session.save(update_fields=["last_seen_at"])
        request.vridhi_account = account
        request.vridhi_membership = membership
        principal = InternalPrincipal(
            principal_id=session.principal_id,
            tenant_id=session.tenant_id,
        )
        return principal, session
