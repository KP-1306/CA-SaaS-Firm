"""C4 ownership and controller authorization for the Work domain.

Small, Work-domain-local helpers that decide who controls a WorkItem at each
workflow status. These are plain functions over the existing models
(WorkItem, Employee), the existing InternalPrincipal, and existing tenant
boundaries. They are intentionally not a generic policy engine, controller
registry, configurable framework or cross-domain abstraction.

The rules implement the approved C4 matrix exactly:

    NOT_STARTED / IN_PROGRESS / REWORK_REQUIRED -> owner controls (edit)
    READY_FOR_REVIEW                            -> reviewer controls (review only)
    WAITING_FOR_CLIENT                          -> internal read-only
    COMPLETED / CANCELLED                        -> terminal, read-only

Deletion is never granted by these helpers (see can_delete, which is always
False): existing DELETE paths would physically destroy attachment/review/audit
history, so C4 blocks them rather than introduce soft deletion.
"""

from __future__ import annotations

import uuid

from contexts.identity.models import Employee

from .models import WorkStatus

# Controller labels exposed to the API/frontend.
CONTROLLER_OWNER = "OWNER"
CONTROLLER_REVIEWER = "REVIEWER"
CONTROLLER_CLIENT = "CLIENT"
CONTROLLER_NONE = "NONE"

_OWNER_CONTROL_STATES = frozenset(
    {WorkStatus.NOT_STARTED, WorkStatus.IN_PROGRESS, WorkStatus.REWORK_REQUIRED}
)
_TERMINAL_STATES = frozenset({WorkStatus.COMPLETED, WorkStatus.CANCELLED})


def is_terminal_state(status) -> bool:
    """Return True for COMPLETED or CANCELLED."""
    return status in _TERMINAL_STATES


def _as_uuid(value):
    """Best-effort UUID coercion; return None if the value is empty/malformed."""
    if value is None or value == "":
        return None
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except (ValueError, AttributeError, TypeError):
        return None


def _is_linked_employee(tenant_id, employee_user_id, principal) -> bool:
    """True when the principal resolves to the given employee id in-tenant.

    Uses the existing Employee-to-principal mapping exactly: an active Employee
    row whose ``id`` equals the WorkItem owner/reviewer field and whose
    ``principal_id`` equals the caller's principal id.
    """
    if not employee_user_id or principal is None:
        return False
    return Employee.objects.filter(
        tenant_id=tenant_id,
        id=employee_user_id,
        principal_id=principal.principal_id,
        is_active=True,
    ).exists()


def is_owner(item, principal) -> bool:
    """True when the acting principal is the assigned owner of the item.

    Two source-proven owner representations are accepted, and nothing else:

    A. Legacy raw-principal: ``owner_user_id`` stores the principal id directly.
       Owner is true when it equals ``principal.principal_id``.
    B. Canonical Employee: ``owner_user_id`` stores an ``Employee.id``. Owner is
       true when an active Employee in the same tenant has that id and
       ``principal_id == principal.principal_id``.

    A non-empty ``owner_user_id`` that matches neither means the actor is not
    the owner (fail closed). An absent owner is not ownership either.
    """
    if principal is None or not item.owner_user_id:
        return False
    owner_uuid = _as_uuid(item.owner_user_id)
    principal_uuid = _as_uuid(principal.principal_id)
    if owner_uuid is not None and principal_uuid is not None and owner_uuid == principal_uuid:
        return True  # representation A: raw principal
    return _is_linked_employee(item.tenant_id, item.owner_user_id, principal)  # representation B


def is_reviewer(item, principal) -> bool:
    """True when the principal is the assigned, active reviewer of the item."""
    return _is_linked_employee(item.tenant_id, item.reviewer_user_id, principal)


def current_controller(item) -> str:
    """Return the controlling role label for the item's current status."""
    status = item.status
    if status in _OWNER_CONTROL_STATES:
        return CONTROLLER_OWNER
    if status == WorkStatus.READY_FOR_REVIEW:
        return CONTROLLER_REVIEWER
    if status == WorkStatus.WAITING_FOR_CLIENT:
        return CONTROLLER_CLIENT
    return CONTROLLER_NONE


def can_edit_work_item(item, principal) -> bool:
    """Owner may edit only in owner-controlled, non-terminal states."""
    if item.status not in _OWNER_CONTROL_STATES:
        return False
    return is_owner(item, principal)


def can_submit_for_review(item, principal) -> bool:
    """Assigned owner may submit only from IN_PROGRESS (existing table)."""
    if item.status != WorkStatus.IN_PROGRESS:
        return False
    return is_owner(item, principal)


def can_review_work_item(item, principal) -> bool:
    """Assigned reviewer may act only in READY_FOR_REVIEW."""
    if item.status != WorkStatus.READY_FOR_REVIEW:
        return False
    return is_reviewer(item, principal)


def can_upload_internal(item, principal) -> bool:
    """Internal upload follows owner edit authority (owner states only)."""
    return can_edit_work_item(item, principal)


def can_mutate_document_request(item, principal) -> bool:
    """Document-request mutation follows owner edit authority."""
    return can_edit_work_item(item, principal)


def can_verify_document_request(item, principal) -> bool:
    """Waiver / attachment accept-reject is a reviewer action in review."""
    return can_review_work_item(item, principal)


def can_review_attachment(item, principal) -> bool:
    """Attachment review is a reviewer action in READY_FOR_REVIEW."""
    return can_review_work_item(item, principal)


def can_delete(item, principal) -> bool:
    """C4 never grants deletion.

    Existing DELETE paths would physically destroy attachment history,
    accepted/rejected evidence, superseded versions and audit records. C4
    blocks these destructive paths rather than introducing soft deletion.
    """
    return False
