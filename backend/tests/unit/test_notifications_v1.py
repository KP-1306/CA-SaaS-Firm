from __future__ import annotations

from types import SimpleNamespace
import uuid

import pytest
from django.test import Client as HttpClient

from contexts.identity.models import Employee
from contexts.notifications.models import (
    Notification,
    NotificationType,
)
from contexts.notifications.services import (
    notify_work_assigned,
    notify_work_transition,
    resolve_recipient_principal_id,
)


TENANT_A = uuid.UUID(
    "11111111-1111-1111-1111-111111111111"
)
TENANT_B = uuid.UUID(
    "33333333-3333-3333-3333-333333333333"
)
ACTOR = uuid.UUID(
    "22222222-2222-2222-2222-222222222222"
)
OWNER_PRINCIPAL = uuid.UUID(
    "44444444-4444-4444-4444-444444444444"
)
REVIEWER_PRINCIPAL = uuid.UUID(
    "55555555-5555-5555-5555-555555555555"
)


def employee(principal, name):
    return Employee.objects.create(
        tenant_id=TENANT_A,
        created_by=ACTOR,
        updated_by=ACTOR,
        name=name,
        email=f"{name.lower()}@example.com",
        role="STAFF",
        principal_id=principal,
        is_active=True,
    )


def work(owner_id, reviewer_id):
    return SimpleNamespace(
        id=uuid.uuid4(),
        tenant_id=TENANT_A,
        title="GST Return",
        owner_user_id=owner_id,
        reviewer_user_id=reviewer_id,
    )


@pytest.mark.django_db
def test_employee_identity_resolves_to_login_principal():
    owner = employee(
        OWNER_PRINCIPAL,
        "Owner",
    )

    resolved = resolve_recipient_principal_id(
        tenant_id=TENANT_A,
        identity_id=owner.id,
    )

    assert resolved == OWNER_PRINCIPAL


@pytest.mark.django_db
def test_raw_principal_identity_remains_supported():
    resolved = resolve_recipient_principal_id(
        tenant_id=TENANT_A,
        identity_id=OWNER_PRINCIPAL,
    )

    assert resolved == OWNER_PRINCIPAL


@pytest.mark.django_db
def test_assignment_notification_targets_owner_principal():
    owner = employee(
        OWNER_PRINCIPAL,
        "Owner",
    )

    item = work(
        owner.id,
        None,
    )

    notify_work_assigned(
        item=item,
        actor_principal_id=ACTOR,
    )

    notification = Notification.objects.get()

    assert (
        notification.notification_type
        == NotificationType.WORK_ASSIGNED
    )
    assert (
        notification.recipient_principal_id
        == OWNER_PRINCIPAL
    )
    assert notification.entity_id == item.id


@pytest.mark.django_db
def test_review_rework_and_completion_notifications():
    owner = employee(
        OWNER_PRINCIPAL,
        "Owner",
    )
    reviewer = employee(
        REVIEWER_PRINCIPAL,
        "Reviewer",
    )

    item = work(
        owner.id,
        reviewer.id,
    )

    notify_work_transition(
        item=item,
        previous_status="IN_PROGRESS",
        target_status="READY_FOR_REVIEW",
        actor_principal_id=OWNER_PRINCIPAL,
    )

    notify_work_transition(
        item=item,
        previous_status="READY_FOR_REVIEW",
        target_status="REWORK_REQUIRED",
        actor_principal_id=REVIEWER_PRINCIPAL,
    )

    notify_work_transition(
        item=item,
        previous_status="READY_FOR_REVIEW",
        target_status="COMPLETED",
        actor_principal_id=REVIEWER_PRINCIPAL,
    )

    rows = list(
        Notification.objects.order_by(
            "created_at"
        )
    )

    assert [
        row.notification_type
        for row in rows
    ] == [
        NotificationType.REVIEW_REQUESTED,
        NotificationType.REWORK_REQUESTED,
        NotificationType.WORK_COMPLETED,
    ]

    assert (
        rows[0].recipient_principal_id
        == REVIEWER_PRINCIPAL
    )
    assert (
        rows[1].recipient_principal_id
        == OWNER_PRINCIPAL
    )
    assert (
        rows[2].recipient_principal_id
        == OWNER_PRINCIPAL
    )


@pytest.mark.django_db
def test_notification_api_is_recipient_and_tenant_scoped():
    own = Notification.objects.create(
        tenant_id=TENANT_A,
        created_by=ACTOR,
        updated_by=ACTOR,
        recipient_principal_id=OWNER_PRINCIPAL,
        notification_type=NotificationType.WORK_ASSIGNED,
        title="Visible",
    )

    Notification.objects.create(
        tenant_id=TENANT_A,
        created_by=ACTOR,
        updated_by=ACTOR,
        recipient_principal_id=REVIEWER_PRINCIPAL,
        notification_type=NotificationType.WORK_ASSIGNED,
        title="Other user",
    )

    Notification.objects.create(
        tenant_id=TENANT_B,
        created_by=ACTOR,
        updated_by=ACTOR,
        recipient_principal_id=OWNER_PRINCIPAL,
        notification_type=NotificationType.WORK_ASSIGNED,
        title="Other tenant",
    )

    http = HttpClient()

    response = http.get(
        "/api/v1/notifications/",
        HTTP_X_TENANT_ID=str(TENANT_A),
        HTTP_X_PRINCIPAL_ID=str(OWNER_PRINCIPAL),
    )

    assert response.status_code == 200

    payload = response.json()
    rows = (
        payload["results"]
        if isinstance(payload, dict)
        and "results" in payload
        else payload
    )

    assert len(rows) == 1
    assert rows[0]["id"] == str(own.id)


@pytest.mark.django_db
def test_notification_can_be_marked_read():
    notification = Notification.objects.create(
        tenant_id=TENANT_A,
        created_by=ACTOR,
        updated_by=ACTOR,
        recipient_principal_id=OWNER_PRINCIPAL,
        notification_type=NotificationType.WORK_ASSIGNED,
        title="Read me",
    )

    http = HttpClient()

    response = http.post(
        f"/api/v1/notifications/{notification.id}/read/",
        data={},
        content_type="application/json",
        HTTP_X_TENANT_ID=str(TENANT_A),
        HTTP_X_PRINCIPAL_ID=str(OWNER_PRINCIPAL),
    )

    assert response.status_code == 200

    notification.refresh_from_db()

    assert notification.read_at is not None
