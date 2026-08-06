from __future__ import annotations

import secrets
import string
from typing import Any

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework import exceptions

from .auth_service import record_auth_event, revoke_session
from .models import (
    AuthenticationEventType,
    AuthenticationOutcome,
    AuthSession,
    Employee,
    MembershipStatus,
    ProviderMembership,
    ProviderRole,
    UserAccount,
    UserAccountStatus,
)

ADMIN_ROLES = frozenset(
    {
        ProviderRole.PLATFORM_ADMIN,
        ProviderRole.OPERATIONS_ADMIN,
    }
)


def require_provider_admin(request: Any) -> ProviderMembership:
    membership = getattr(request, "vridhi_membership", None)
    if membership is None or membership.status != MembershipStatus.ACTIVE:
        raise exceptions.PermissionDenied("An active Vridhi membership is required.")
    if membership.role not in ADMIN_ROLES:
        record_auth_event(
            request=request,
            event_type=AuthenticationEventType.ACCESS_DENIED,
            outcome=AuthenticationOutcome.DENIED,
            account=getattr(request, "vridhi_account", None),
            membership=membership,
            session=getattr(request, "auth", None),
            reason="CONSULTANT_ADMIN_REQUIRED",
        )
        raise exceptions.PermissionDenied("Vridhi administrator access is required.")
    return membership


def _temporary_password() -> str:
    alphabet = string.ascii_letters + string.digits + "!@#$%&*"
    while True:
        password = "".join(secrets.choice(alphabet) for _ in range(18))
        if (
            any(c.islower() for c in password)
            and any(c.isupper() for c in password)
            and any(c.isdigit() for c in password)
            and any(c in "!@#$%&*" for c in password)
        ):
            return password


def serialize_consultant(
    account: UserAccount,
    membership: ProviderMembership,
) -> dict[str, Any]:
    employee = None
    if membership.employee_id:
        employee = Employee.objects.filter(
            tenant_id=membership.tenant_id,
            id=membership.employee_id,
        ).first()

    active_sessions = AuthSession.objects.filter(
        user_account_id=account.id,
        revoked_at__isnull=True,
        expires_at__gt=timezone.now(),
    ).count()

    return {
        "id": str(account.id),
        "email": account.email,
        "display_name": account.display_name,
        "account_status": account.status,
        "email_verified": account.email_verified_at is not None,
        "must_change_password": account.must_change_password,
        "invitation_sent_at": account.invitation_sent_at,
        "last_login_at": account.last_login_at,
        "failed_login_count": account.failed_login_count,
        "locked_until": account.locked_until,
        "membership": {
            "id": str(membership.id),
            "role": membership.role,
            "status": membership.status,
            "effective_from": membership.effective_from,
            "effective_to": membership.effective_to,
            "employee_id": (
                str(membership.employee_id)
                if membership.employee_id
                else None
            ),
        },
        "employee": (
            {
                "id": str(employee.id),
                "name": employee.name,
                "email": employee.email,
                "role": employee.role,
                "is_active": employee.is_active,
            }
            if employee
            else None
        ),
        "active_session_count": active_sessions,
        "created_at": account.created_at,
        "updated_at": account.updated_at,
    }


def create_consultant(
    *,
    request: Any,
    email: str,
    display_name: str,
    role: str,
    employee_id: str | None = None,
) -> tuple[UserAccount, ProviderMembership, str]:
    admin = require_provider_admin(request)
    normalized_email = (email or "").strip().lower()

    if UserAccount.objects.filter(email=normalized_email).exists():
        raise exceptions.ValidationError(
            {"email": "A user account with this email already exists."}
        )

    if role not in ProviderRole.values:
        raise exceptions.ValidationError({"role": "Invalid provider role."})

    employee = None
    if employee_id:
        employee = Employee.objects.filter(
            tenant_id=admin.tenant_id,
            id=employee_id,
        ).first()
        if employee is None:
            raise exceptions.ValidationError(
                {"employee_id": "Employee was not found in the Vridhi tenant."}
            )
        if ProviderMembership.objects.filter(
            tenant_id=admin.tenant_id,
            employee_id=employee.id,
            status=MembershipStatus.ACTIVE,
        ).exists():
            raise exceptions.ValidationError(
                {"employee_id": "This employee already has an active login membership."}
            )

    temporary_password = _temporary_password()
    now = timezone.now()

    with transaction.atomic():
        account = UserAccount(
            email=normalized_email,
            display_name=(display_name or "").strip(),
            status=UserAccountStatus.ACTIVE,
            must_change_password=True,
            invitation_sent_at=now,
            invited_by_principal_id=request.user.principal_id,
            activated_at=now,
        )
        account.set_password(temporary_password)
        account.save()

        membership = ProviderMembership.objects.create(
            tenant_id=admin.tenant_id,
            created_by=request.user.principal_id,
            updated_by=request.user.principal_id,
            user_account_id=account.id,
            employee_id=employee.id if employee else None,
            role=role,
            status=MembershipStatus.ACTIVE,
        )

        if employee is not None and employee.principal_id != membership.employee_id:
            employee.principal_id = membership.employee_id
            employee.updated_by = request.user.principal_id
            employee.save(update_fields=["principal_id", "updated_by"])

        record_auth_event(
            request=request,
            event_type=AuthenticationEventType.MEMBERSHIP_CHANGED,
            outcome=AuthenticationOutcome.SUCCESS,
            account=account,
            membership=membership,
            session=getattr(request, "auth", None),
            reason="CONSULTANT_CREATED",
            metadata={
                "role": role,
                "employee_id": employee.id if employee else "",
                "invited_by": request.user.principal_id,
            },
        )

    return account, membership, temporary_password


def set_consultant_status(
    *,
    request: Any,
    account: UserAccount,
    membership: ProviderMembership,
    status_value: str,
    reason: str,
) -> None:
    require_provider_admin(request)
    if status_value not in UserAccountStatus.values:
        raise exceptions.ValidationError({"status": "Invalid account status."})

    previous = account.status
    now = timezone.now()

    with transaction.atomic():
        account.status = status_value
        if status_value == UserAccountStatus.ACTIVE:
            account.activated_at = now
        account.save(update_fields=["status", "activated_at", "updated_at"])

        if status_value == UserAccountStatus.ACTIVE:
            membership.status = MembershipStatus.ACTIVE
            membership.effective_to = None
        elif status_value == UserAccountStatus.SUSPENDED:
            membership.status = MembershipStatus.SUSPENDED
        else:
            membership.status = MembershipStatus.ENDED
            membership.effective_to = now

        membership.updated_by = request.user.principal_id
        membership.save(
            update_fields=[
                "status",
                "effective_to",
                "updated_by",
                "updated_at",
            ]
        )

        if status_value != UserAccountStatus.ACTIVE:
            for session in AuthSession.objects.filter(
                user_account_id=account.id,
                revoked_at__isnull=True,
                expires_at__gt=now,
            ):
                revoke_session(
                    request=request,
                    session=session,
                    reason=f"ACCOUNT_{status_value}",
                )

        record_auth_event(
            request=request,
            event_type=AuthenticationEventType.ACCOUNT_STATUS_CHANGED,
            outcome=AuthenticationOutcome.SUCCESS,
            account=account,
            membership=membership,
            session=getattr(request, "auth", None),
            reason=(reason or "ADMIN_STATUS_CHANGE")[:200],
            metadata={
                "previous_status": previous,
                "new_status": status_value,
                "changed_by": request.user.principal_id,
            },
        )


def change_consultant_role(
    *,
    request: Any,
    account: UserAccount,
    membership: ProviderMembership,
    role: str,
    reason: str,
) -> None:
    require_provider_admin(request)
    if role not in ProviderRole.values:
        raise exceptions.ValidationError({"role": "Invalid provider role."})

    previous = membership.role
    membership.role = role
    membership.updated_by = request.user.principal_id
    membership.save(update_fields=["role", "updated_by", "updated_at"])

    record_auth_event(
        request=request,
        event_type=AuthenticationEventType.MEMBERSHIP_CHANGED,
        outcome=AuthenticationOutcome.SUCCESS,
        account=account,
        membership=membership,
        session=getattr(request, "auth", None),
        reason=(reason or "ADMIN_ROLE_CHANGE")[:200],
        metadata={
            "previous_role": previous,
            "new_role": role,
            "changed_by": request.user.principal_id,
        },
    )


def link_employee(
    *,
    request: Any,
    account: UserAccount,
    membership: ProviderMembership,
    employee_id: str,
) -> Employee:
    require_provider_admin(request)
    employee = Employee.objects.filter(
        tenant_id=membership.tenant_id,
        id=employee_id,
    ).first()
    if employee is None:
        raise exceptions.ValidationError(
            {"employee_id": "Employee was not found in the Vridhi tenant."}
        )

    conflicting = ProviderMembership.objects.filter(
        tenant_id=membership.tenant_id,
        employee_id=employee.id,
        status=MembershipStatus.ACTIVE,
    ).exclude(id=membership.id)
    if conflicting.exists():
        raise exceptions.ValidationError(
            {"employee_id": "Employee is already linked to another active account."}
        )

    previous = membership.employee_id
    with transaction.atomic():
        membership.employee_id = employee.id
        membership.updated_by = request.user.principal_id
        membership.save(
            update_fields=["employee_id", "updated_by", "updated_at"]
        )
        employee.principal_id = employee.id
        employee.updated_by = request.user.principal_id
        employee.save(update_fields=["principal_id", "updated_by"])

        record_auth_event(
            request=request,
            event_type=AuthenticationEventType.MEMBERSHIP_CHANGED,
            outcome=AuthenticationOutcome.SUCCESS,
            account=account,
            membership=membership,
            session=getattr(request, "auth", None),
            reason="EMPLOYEE_LINK_CHANGED",
            metadata={
                "previous_employee_id": previous or "",
                "new_employee_id": employee.id,
                "changed_by": request.user.principal_id,
            },
        )
    return employee


def reset_consultant_password(
    *,
    request: Any,
    account: UserAccount,
    membership: ProviderMembership,
) -> str:
    require_provider_admin(request)
    temporary_password = _temporary_password()
    with transaction.atomic():
        account.set_password(temporary_password)
        account.must_change_password = True
        account.failed_login_count = 0
        account.locked_until = None
        account.save(
            update_fields=[
                "password_hash",
                "password_changed_at",
                "must_change_password",
                "failed_login_count",
                "locked_until",
                "updated_at",
            ]
        )
        for session in AuthSession.objects.filter(
            user_account_id=account.id,
            revoked_at__isnull=True,
            expires_at__gt=timezone.now(),
        ):
            revoke_session(
                request=request,
                session=session,
                reason="ADMIN_PASSWORD_RESET",
            )
        record_auth_event(
            request=request,
            event_type=AuthenticationEventType.PASSWORD_CHANGED,
            outcome=AuthenticationOutcome.SUCCESS,
            account=account,
            membership=membership,
            session=getattr(request, "auth", None),
            reason="ADMIN_PASSWORD_RESET",
            metadata={"changed_by": request.user.principal_id},
        )
    return temporary_password


def unlock_consultant(
    *,
    request: Any,
    account: UserAccount,
    membership: ProviderMembership,
) -> None:
    require_provider_admin(request)
    account.failed_login_count = 0
    account.locked_until = None
    account.save(
        update_fields=["failed_login_count", "locked_until", "updated_at"]
    )
    record_auth_event(
        request=request,
        event_type=AuthenticationEventType.ACCOUNT_STATUS_CHANGED,
        outcome=AuthenticationOutcome.SUCCESS,
        account=account,
        membership=membership,
        session=getattr(request, "auth", None),
        reason="ADMIN_UNLOCK",
        metadata={"changed_by": request.user.principal_id},
    )


def revoke_all_consultant_sessions(
    *,
    request: Any,
    account: UserAccount,
) -> int:
    require_provider_admin(request)
    count = 0
    for session in AuthSession.objects.filter(
        user_account_id=account.id,
        revoked_at__isnull=True,
        expires_at__gt=timezone.now(),
    ):
        revoke_session(
            request=request,
            session=session,
            reason="ADMIN_REVOKED_ALL",
        )
        count += 1
    return count
