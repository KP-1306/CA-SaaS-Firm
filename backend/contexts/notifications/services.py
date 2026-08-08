from __future__ import annotations

import logging
from uuid import UUID

from django.db import transaction

from contexts.identity.models import Employee

from .models import Notification, NotificationType


logger = logging.getLogger(__name__)


def _uuid(value) -> UUID | None:
    if value in (None, ""):
        return None

    try:
        return UUID(str(value))
    except (TypeError, ValueError):
        return None


def resolve_recipient_principal_id(
    *,
    tenant_id,
    identity_id,
) -> UUID | None:
    """Resolve Work identity storage to the canonical login principal.

    Work ownership historically supports both Employee.id and raw principal
    UUIDs. Notifications must always target the login principal because the
    notification API is principal-scoped.
    """

    identity_uuid = _uuid(identity_id)

    if identity_uuid is None:
        return None

    employee = (
        Employee.objects.filter(
            tenant_id=tenant_id,
            id=identity_uuid,
        )
        .only("principal_id")
        .first()
    )

    if employee is not None:
        return employee.principal_id

    # No Employee row means the stored value may already be a principal UUID.
    return identity_uuid


def create_notification(
    *,
    tenant_id,
    recipient_principal_id,
    notification_type: str,
    title: str,
    actor_principal_id,
    message: str = "",
    entity_type: str = "",
    entity_id=None,
    metadata: dict | None = None,
) -> Notification:
    if notification_type not in NotificationType.values:
        raise ValueError(
            f"Unsupported notification type: {notification_type}"
        )

    return Notification.objects.create(
        tenant_id=tenant_id,
        recipient_principal_id=recipient_principal_id,
        notification_type=notification_type,
        title=title,
        message=message,
        entity_type=entity_type,
        entity_id=entity_id,
        metadata=metadata or {},
        created_by=actor_principal_id,
        updated_by=actor_principal_id,
    )


def _safe_create_notification(**kwargs):
    """Notifications must never break the certified business workflow.

    The inner atomic block provides a savepoint when called from an existing
    transaction. A notification persistence failure rolls back only the
    notification attempt, not Assignment / Review / Completion.
    """

    try:
        with transaction.atomic():
            return create_notification(**kwargs)
    except Exception:  # noqa: BLE001
        logger.exception(
            "Notification persistence failed.",
        )
        return None


def notify_work_assigned(
    *,
    item,
    actor_principal_id,
):
    recipient = resolve_recipient_principal_id(
        tenant_id=item.tenant_id,
        identity_id=item.owner_user_id,
    )

    if recipient is None:
        return None

    return _safe_create_notification(
        tenant_id=item.tenant_id,
        recipient_principal_id=recipient,
        notification_type=NotificationType.WORK_ASSIGNED,
        title="Work assigned",
        message=f'You have been assigned "{item.title}".',
        actor_principal_id=actor_principal_id,
        entity_type="WorkItem",
        entity_id=item.id,
        metadata={
            "work_item_id": str(item.id),
        },
    )


def notify_work_transition(
    *,
    item,
    previous_status: str,
    target_status: str,
    actor_principal_id,
):
    recipient_identity = None
    notification_type = None
    title = ""
    message = ""

    if target_status == "READY_FOR_REVIEW":
        recipient_identity = item.reviewer_user_id
        notification_type = NotificationType.REVIEW_REQUESTED
        title = "Review requested"
        message = f'"{item.title}" is ready for your review.'

    elif target_status == "REWORK_REQUIRED":
        recipient_identity = item.owner_user_id
        notification_type = NotificationType.REWORK_REQUESTED
        title = "Rework required"
        message = f'"{item.title}" has been returned for rework.'

    elif target_status == "COMPLETED":
        recipient_identity = item.owner_user_id
        notification_type = NotificationType.WORK_COMPLETED
        title = "Work completed"
        message = f'"{item.title}" has been approved and completed.'

    if notification_type is None:
        return None

    recipient = resolve_recipient_principal_id(
        tenant_id=item.tenant_id,
        identity_id=recipient_identity,
    )

    if recipient is None:
        return None

    return _safe_create_notification(
        tenant_id=item.tenant_id,
        recipient_principal_id=recipient,
        notification_type=notification_type,
        title=title,
        message=message,
        actor_principal_id=actor_principal_id,
        entity_type="WorkItem",
        entity_id=item.id,
        metadata={
            "work_item_id": str(item.id),
            "previous_status": str(previous_status),
            "status": str(target_status),
        },
    )
