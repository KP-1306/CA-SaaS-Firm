from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest

from contexts.identity.models import (
    MembershipStatus,
    ProviderMembership,
    ProviderRole,
)
from contexts.work import ownership
from contexts.work.models import WorkStatus


TENANT = uuid.UUID(
    "11111111-1111-1111-1111-111111111111"
)

ADMIN = uuid.UUID(
    "22222222-2222-2222-2222-222222222222"
)

OTHER = uuid.UUID(
    "33333333-3333-3333-3333-333333333333"
)


def principal(principal_id=ADMIN):
    return SimpleNamespace(
        principal_id=principal_id,
        tenant_id=TENANT,
    )


def item(status):
    return SimpleNamespace(
        tenant_id=TENANT,
        owner_user_id=OTHER,
        reviewer_user_id=OTHER,
        status=status,
    )


def create_membership(role):
    return ProviderMembership.objects.create(
        tenant_id=TENANT,
        created_by=ADMIN,
        updated_by=ADMIN,
        user_account_id=ADMIN,
        role=role,
        status=MembershipStatus.ACTIVE,
    )


@pytest.mark.django_db
def test_platform_admin_is_operational_superuser():
    create_membership(
        ProviderRole.PLATFORM_ADMIN
    )

    assert ownership.is_operational_superuser(
        TENANT,
        principal(),
    )


@pytest.mark.django_db
def test_platform_admin_can_assume_owner_control():
    create_membership(
        ProviderRole.PLATFORM_ADMIN
    )

    work = item(
        WorkStatus.IN_PROGRESS
    )

    assert ownership.is_owner(
        work,
        principal(),
    )

    assert ownership.can_edit_work_item(
        work,
        principal(),
    )

    assert ownership.can_submit_for_review(
        work,
        principal(),
    )


@pytest.mark.django_db
def test_platform_admin_can_assume_reviewer_control():
    create_membership(
        ProviderRole.PLATFORM_ADMIN
    )

    work = item(
        WorkStatus.READY_FOR_REVIEW
    )

    assert ownership.is_reviewer(
        work,
        principal(),
    )

    assert ownership.can_review_work_item(
        work,
        principal(),
    )

    assert ownership.can_review_attachment(
        work,
        principal(),
    )


@pytest.mark.django_db
def test_terminal_work_remains_immutable():
    create_membership(
        ProviderRole.PLATFORM_ADMIN
    )

    for status in (
        WorkStatus.COMPLETED,
        WorkStatus.CANCELLED,
    ):
        work = item(status)

        assert not ownership.can_edit_work_item(
            work,
            principal(),
        )

        assert not ownership.can_review_work_item(
            work,
            principal(),
        )

        assert not ownership.can_upload_internal(
            work,
            principal(),
        )


@pytest.mark.django_db
def test_operations_admin_does_not_get_unconditional_override():
    create_membership(
        ProviderRole.OPERATIONS_ADMIN
    )

    work = item(
        WorkStatus.READY_FOR_REVIEW
    )

    assert not ownership.is_operational_superuser(
        TENANT,
        principal(),
    )

    assert not ownership.is_reviewer(
        work,
        principal(),
    )


@pytest.mark.django_db
def test_cross_tenant_platform_admin_cannot_override():
    create_membership(
        ProviderRole.PLATFORM_ADMIN
    )

    foreign = SimpleNamespace(
        principal_id=ADMIN,
        tenant_id=uuid.uuid4(),
    )

    assert not ownership.is_operational_superuser(
        TENANT,
        foreign,
    )
