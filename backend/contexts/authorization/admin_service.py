from __future__ import annotations

from typing import Any
from uuid import UUID

from django.db import transaction
from rest_framework import exceptions

from contexts.authorization.models import (
    Access,
    AccessProfile,
    RoleAccess,
    RoleTemplate,
)
from contexts.authorization.services import (
    resolve_effective_access,
    sync_system_access_catalogue,
)
from contexts.identity.auth_service import record_auth_event
from contexts.identity.consultant_admin_service import require_provider_admin
from contexts.identity.models import (
    AuthenticationEventType,
    AuthenticationOutcome,
    UserAccount,
)


def _tenant_id(request: Any) -> UUID:
    return require_provider_admin(request).tenant_id


def _validate_access_codes(codes: list[str]) -> list[Access]:
    normalized = list(dict.fromkeys(codes))
    rows = list(
        Access.objects.filter(
            code__in=normalized,
            is_active=True,
        )
    )
    found = {row.code for row in rows}
    missing = sorted(set(normalized) - found)

    if missing:
        raise exceptions.ValidationError(
            {"access_codes": [f"Unknown access code: {code}" for code in missing]}
        )

    return rows


def list_roles(request: Any):
    tenant_id = _tenant_id(request)
    sync_system_access_catalogue()

    return (
        RoleTemplate.objects.filter(
            is_active=True,
        )
        .filter(
            models.Q(tenant_id__isnull=True)
            | models.Q(tenant_id=tenant_id)
        )
        .prefetch_related("role_access__access")
        .order_by("-is_system", "name")
    )


def get_role_for_tenant(*, request: Any, role_id: int) -> RoleTemplate:
    tenant_id = _tenant_id(request)
    role = (
        RoleTemplate.objects.prefetch_related("role_access__access")
        .filter(id=role_id)
        .filter(
            models.Q(tenant_id__isnull=True)
            | models.Q(tenant_id=tenant_id)
        )
        .first()
    )
    if role is None:
        raise exceptions.NotFound("Role was not found.")
    return role


@transaction.atomic
def create_role(
    *,
    request: Any,
    code: str,
    name: str,
    description: str = "",
    access_codes: list[str] | None = None,
) -> RoleTemplate:
    tenant_id = _tenant_id(request)
    normalized_code = code.strip().upper()

    if RoleTemplate.objects.filter(
        tenant_id=tenant_id,
        code=normalized_code,
    ).exists():
        raise exceptions.ValidationError(
            {"code": "A role with this code already exists for the firm."}
        )

    role = RoleTemplate.objects.create(
        tenant_id=tenant_id,
        code=normalized_code,
        name=name.strip(),
        description=description.strip(),
        is_system=False,
        is_active=True,
    )

    for access in _validate_access_codes(access_codes or []):
        RoleAccess.objects.create(role=role, access=access)

    return role


@transaction.atomic
def update_role(
    *,
    request: Any,
    role: RoleTemplate,
    values: dict,
) -> RoleTemplate:
    _tenant_id(request)

    if role.is_system:
        raise exceptions.ValidationError(
            {"role": "System roles cannot be modified."}
        )

    fields = []

    for field in ("name", "description", "is_active"):
        if field in values:
            setattr(role, field, values[field])
            fields.append(field)

    if fields:
        fields.append("updated_at")
        role.save(update_fields=fields)

    if "access_codes" in values:
        accesses = _validate_access_codes(values["access_codes"])
        RoleAccess.objects.filter(role=role).delete()
        RoleAccess.objects.bulk_create(
            [
                RoleAccess(role=role, access=access)
                for access in accesses
            ]
        )

    return role


@transaction.atomic
def clone_role(
    *,
    request: Any,
    source: RoleTemplate,
    code: str,
    name: str,
) -> RoleTemplate:
    tenant_id = _tenant_id(request)
    normalized_code = code.strip().upper()

    if RoleTemplate.objects.filter(
        tenant_id=tenant_id,
        code=normalized_code,
    ).exists():
        raise exceptions.ValidationError(
            {"code": "A role with this code already exists for the firm."}
        )

    target = RoleTemplate.objects.create(
        tenant_id=tenant_id,
        code=normalized_code,
        name=name.strip(),
        description=source.description,
        is_system=False,
        is_active=True,
    )

    RoleAccess.objects.bulk_create(
        [
            RoleAccess(role=target, access=mapping.access)
            for mapping in source.role_access.select_related("access")
            if mapping.access.is_active
        ]
    )

    return target


@transaction.atomic
def save_access_profile(
    *,
    request: Any,
    account_id: UUID,
    values: dict,
) -> AccessProfile:
    tenant_id = _tenant_id(request)

    account = UserAccount.objects.filter(id=account_id).first()
    if account is None:
        raise exceptions.NotFound("User account was not found.")

    role = None
    role_id = values.get("role_id")

    if role_id is not None:
        role = get_role_for_tenant(
            request=request,
            role_id=role_id,
        )
        if not role.is_active:
            raise exceptions.ValidationError(
                {"role_id": "Inactive roles cannot be assigned."}
            )

    additional = _validate_access_codes(
        values.get("additional_access_codes", [])
    )

    profile, _ = AccessProfile.objects.update_or_create(
        tenant_id=tenant_id,
        user_account_id=account.id,
        defaults={
            "role": role,
            "department_ids": [
                str(value)
                for value in values.get("department_ids", [])
            ],
            "team_ids": [
                str(value)
                for value in values.get("team_ids", [])
            ],
            "service_ids": [
                str(value)
                for value in values.get("service_ids", [])
            ],
            "is_active": values.get("is_active", True),
        },
    )

    profile.additional_access.set(additional)

    record_auth_event(
        request=request,
        event_type=AuthenticationEventType.MEMBERSHIP_CHANGED,
        outcome=AuthenticationOutcome.SUCCESS,
        account=account,
        membership=getattr(request, "vridhi_membership", None),
        session=getattr(request, "auth", None),
        reason="ACCESS_PROFILE_CHANGED",
        metadata={
            "role_code": role.code if role else "",
            "additional_access_count": len(additional),
            "changed_by": request.user.principal_id,
        },
    )

    return profile


def serialize_profile(*, tenant_id: UUID, account_id: UUID) -> dict:
    profile = (
        AccessProfile.objects.select_related("role")
        .prefetch_related("additional_access")
        .filter(
            tenant_id=tenant_id,
            user_account_id=account_id,
        )
        .first()
    )

    effective = resolve_effective_access(
        tenant_id=tenant_id,
        user_account_id=account_id,
    )

    return {
        "user_account_id": str(account_id),
        "role": (
            {
                "id": profile.role.id,
                "code": profile.role.code,
                "name": profile.role.name,
            }
            if profile and profile.role
            else None
        ),
        "additional_access_codes": (
            sorted(
                access.code
                for access in profile.additional_access.all()
            )
            if profile
            else []
        ),
        "department_ids": profile.department_ids if profile else [],
        "team_ids": profile.team_ids if profile else [],
        "service_ids": profile.service_ids if profile else [],
        "is_active": profile.is_active if profile else False,
        "effective_access_codes": sorted(effective.access_codes),
    }


from django.db import models
