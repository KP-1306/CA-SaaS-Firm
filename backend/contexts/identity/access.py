"""Role-based access resolution for the internal plane.

Uses the existing Employee.role (FirmRole) resolved through the
Employee-to-principal mapping. This is the source-proven authorization basis;
it introduces no new identity model or capability framework.

Executive/audit access is limited to firm leadership (ADMIN, PARTNER).
"""

from __future__ import annotations

import uuid

from .models import (
    Employee,
    FirmRole,
    MembershipStatus,
    ProviderMembership,
    ProviderRole,
)

# Firm-wide sensitive surfaces (executive dashboard, audit viewer).
EXECUTIVE_ROLES = frozenset({FirmRole.ADMIN, FirmRole.PARTNER})


def _as_uuid(value):
    if value is None or value == "":
        return None
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except (ValueError, AttributeError, TypeError):
        return None


def employee_for_principal(tenant_id, principal):
    """Return the active Employee for the acting principal, or None."""
    if principal is None:
        return None
    pid = _as_uuid(getattr(principal, "principal_id", None))
    if pid is None:
        return None
    return (
        Employee.objects.filter(tenant_id=tenant_id, principal_id=pid, is_active=True)
        .order_by("created_at")
        .first()
    )


def caller_role(tenant_id, principal) -> str | None:
    emp = employee_for_principal(tenant_id, principal)
    return emp.role if emp else None


def is_executive(tenant_id, principal) -> bool:
    """True when the caller is firm leadership (ADMIN or PARTNER)."""
    return caller_role(tenant_id, principal) in EXECUTIVE_ROLES


def is_platform_admin(tenant_id, principal) -> bool:
    """Return True only for active tenant-local PLATFORM_ADMIN authority.

    Provider authority is independent of Employee/FirmRole leadership.
    """
    if principal is None:
        return False

    tenant_uuid = _as_uuid(tenant_id)
    principal_tenant = _as_uuid(
        getattr(principal, "tenant_id", None)
    )
    principal_id = _as_uuid(
        getattr(principal, "principal_id", None)
    )

    if (
        tenant_uuid is None
        or principal_tenant != tenant_uuid
        or principal_id is None
    ):
        return False

    memberships = ProviderMembership.objects.filter(
        tenant_id=tenant_uuid,
        role=ProviderRole.PLATFORM_ADMIN,
        status=MembershipStatus.ACTIVE,
    )

    # Unlinked consultant session:
    # AuthSession.principal_id == UserAccount.id.
    if memberships.filter(
        user_account_id=principal_id,
    ).exists():
        return True

    # Linked consultant session:
    # AuthSession.principal_id == ProviderMembership.employee_id.
    if memberships.filter(
        employee_id=principal_id,
    ).exists():
        return True

    # Preserve the canonical Employee.principal_id representation used
    # throughout the internal plane.
    employee_ids = Employee.objects.filter(
        tenant_id=tenant_uuid,
        principal_id=principal_id,
        is_active=True,
    ).values_list(
        "id",
        flat=True,
    )

    return memberships.filter(
        employee_id__in=employee_ids,
    ).exists()


def can_view_firm_operations(tenant_id, principal) -> bool:
    """Read-only firm operational visibility for Mission Control."""
    return (
        is_executive(tenant_id, principal)
        or is_platform_admin(tenant_id, principal)
    )


def caller_identity_ids(tenant_id, principal):
    """All canonical identity references the caller's work may be stored under.

    Work ownership is compatible with two representations (raw principal UUID or
    Employee.id). For dashboard queries we must include BOTH the acting
    principal id and the caller's Employee.id so no owned/reviewed work is
    missed, without double counting (the set is de-duplicated by callers).
    """
    ids = set()
    pid = _as_uuid(getattr(principal, "principal_id", None))
    if pid is not None:
        ids.add(pid)
    emp = employee_for_principal(tenant_id, principal)
    if emp is not None:
        ids.add(emp.id)
    return ids, (emp.id if emp else None)


def identity_ids_for_employee(tenant_id, employee_id):
    """Resolve every supported work identity for an active tenant employee.

    Returns ``({Employee.id, principal_id?}, Employee)``. The tenant and active
    filters prevent leadership lookups from crossing tenant boundaries or using
    inactive employee identities.
    """
    eid = _as_uuid(employee_id)
    if eid is None:
        return set(), None
    emp = (
        Employee.objects.filter(tenant_id=tenant_id, id=eid, is_active=True)
        .order_by("created_at")
        .first()
    )
    if emp is None:
        return set(), None
    ids = {emp.id}
    if emp.principal_id:
        ids.add(emp.principal_id)
    return ids, emp
