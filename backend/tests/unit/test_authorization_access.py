from uuid import uuid4

import pytest

from contexts.authorization.models import (
    Access,
    AccessProfile,
    RoleAccess,
    RoleTemplate,
)
from contexts.authorization.services import (
    has_access,
    resolve_effective_access,
    sync_system_access_catalogue,
)


pytestmark = pytest.mark.django_db


def test_system_catalogue_is_idempotent():
    sync_system_access_catalogue()
    first_roles = RoleTemplate.objects.count()
    first_access = Access.objects.count()
    first_mappings = RoleAccess.objects.count()

    sync_system_access_catalogue()

    assert RoleTemplate.objects.count() == first_roles
    assert Access.objects.count() == first_access
    assert RoleAccess.objects.count() == first_mappings
    assert RoleTemplate.objects.filter(code="PARTNER").exists()
    assert Access.objects.filter(code="access.manage").exists()


def test_role_and_additional_access_are_combined():
    tenant_id = uuid4()
    user_id = uuid4()

    view_access = Access.objects.create(
        module="Clients",
        code="clients.view",
        name="View Clients",
    )
    export_access = Access.objects.create(
        module="Reports",
        code="reports.export",
        name="Export Reports",
    )
    role = RoleTemplate.objects.create(
        tenant_id=tenant_id,
        code="CONSULTANT",
        name="Consultant",
        is_system=False,
    )
    RoleAccess.objects.create(role=role, access=view_access)

    profile = AccessProfile.objects.create(
        tenant_id=tenant_id,
        user_account_id=user_id,
        role=role,
        department_ids=[str(uuid4())],
        team_ids=[str(uuid4())],
        service_ids=[str(uuid4())],
    )
    profile.additional_access.add(export_access)

    effective = resolve_effective_access(
        tenant_id=tenant_id,
        user_account_id=user_id,
    )

    assert effective.role_code == "CONSULTANT"
    assert effective.access_codes == frozenset(
        {"clients.view", "reports.export"}
    )
    assert len(effective.department_ids) == 1
    assert len(effective.team_ids) == 1
    assert len(effective.service_ids) == 1


def test_missing_profile_defaults_to_no_access():
    assert not has_access(
        tenant_id=uuid4(),
        user_account_id=uuid4(),
        access_code="clients.view",
    )


def test_inactive_profile_defaults_to_no_access():
    tenant_id = uuid4()
    user_id = uuid4()
    access = Access.objects.create(
        module="Clients",
        code="clients.view",
        name="View Clients",
    )
    role = RoleTemplate.objects.create(
        tenant_id=tenant_id,
        code="EMPLOYEE",
        name="Employee",
        is_system=False,
    )
    RoleAccess.objects.create(role=role, access=access)
    AccessProfile.objects.create(
        tenant_id=tenant_id,
        user_account_id=user_id,
        role=role,
        is_active=False,
    )

    assert not has_access(
        tenant_id=tenant_id,
        user_account_id=user_id,
        access_code="clients.view",
    )


def test_access_profile_is_tenant_specific():
    user_id = uuid4()
    tenant_a = uuid4()
    tenant_b = uuid4()

    access = Access.objects.create(
        module="Clients",
        code="clients.view",
        name="View Clients",
    )
    role = RoleTemplate.objects.create(
        tenant_id=tenant_a,
        code="CONSULTANT",
        name="Consultant",
        is_system=False,
    )
    RoleAccess.objects.create(role=role, access=access)
    AccessProfile.objects.create(
        tenant_id=tenant_a,
        user_account_id=user_id,
        role=role,
    )

    assert has_access(
        tenant_id=tenant_a,
        user_account_id=user_id,
        access_code="clients.view",
    )
    assert not has_access(
        tenant_id=tenant_b,
        user_account_id=user_id,
        access_code="clients.view",
    )
