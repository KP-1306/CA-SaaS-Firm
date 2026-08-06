from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from django.db import transaction

from contexts.authorization.catalogue import (
    ACCESS_CATALOGUE,
    ROLE_ACCESS_CODES,
    ROLE_TEMPLATES,
)
from contexts.authorization.models import (
    Access,
    AccessProfile,
    RoleAccess,
    RoleTemplate,
)


@dataclass(frozen=True, slots=True)
class EffectiveAccess:
    tenant_id: UUID
    user_account_id: UUID
    role_code: str | None
    access_codes: frozenset[str]
    department_ids: tuple[str, ...]
    team_ids: tuple[str, ...]
    service_ids: tuple[str, ...]

    def allows(self, access_code: str) -> bool:
        return access_code in self.access_codes


@transaction.atomic
def sync_system_access_catalogue() -> None:
    """Create or update Vridhi's small standard access catalogue."""

    access_by_code: dict[str, Access] = {}

    for code, module, name in ACCESS_CATALOGUE:
        access, _ = Access.objects.update_or_create(
            code=code,
            defaults={
                "module": module,
                "name": name,
                "is_active": True,
            },
        )
        access_by_code[code] = access

    for role_data in ROLE_TEMPLATES:
        role, _ = RoleTemplate.objects.update_or_create(
            tenant_id=None,
            code=role_data["code"],
            defaults={
                "name": role_data["name"],
                "description": role_data["description"],
                "is_system": True,
                "is_active": True,
            },
        )

        expected_codes = set(ROLE_ACCESS_CODES[role.code])

        RoleAccess.objects.filter(role=role).exclude(
            access__code__in=expected_codes
        ).delete()

        for code in expected_codes:
            RoleAccess.objects.get_or_create(
                role=role,
                access=access_by_code[code],
            )


def resolve_effective_access(
    *,
    tenant_id: UUID,
    user_account_id: UUID,
) -> EffectiveAccess:
    """Resolve role access plus optional additional access for one tenant user."""

    profile = (
        AccessProfile.objects.select_related("role")
        .prefetch_related(
            "additional_access",
            "role__role_access__access",
        )
        .filter(
            tenant_id=tenant_id,
            user_account_id=user_account_id,
            is_active=True,
        )
        .first()
    )

    if profile is None:
        return EffectiveAccess(
            tenant_id=tenant_id,
            user_account_id=user_account_id,
            role_code=None,
            access_codes=frozenset(),
            department_ids=(),
            team_ids=(),
            service_ids=(),
        )

    access_codes = {
        access.code
        for access in profile.additional_access.all()
        if access.is_active
    }

    role_code = None

    if profile.role is not None and profile.role.is_active:
        role_code = profile.role.code

        access_codes.update(
            mapping.access.code
            for mapping in profile.role.role_access.all()
            if mapping.access.is_active
        )

    return EffectiveAccess(
        tenant_id=tenant_id,
        user_account_id=user_account_id,
        role_code=role_code,
        access_codes=frozenset(access_codes),
        department_ids=tuple(str(value) for value in profile.department_ids),
        team_ids=tuple(str(value) for value in profile.team_ids),
        service_ids=tuple(str(value) for value in profile.service_ids),
    )


def has_access(
    *,
    tenant_id: UUID,
    user_account_id: UUID,
    access_code: str,
) -> bool:
    return resolve_effective_access(
        tenant_id=tenant_id,
        user_account_id=user_account_id,
    ).allows(access_code)
