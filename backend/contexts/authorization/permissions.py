from __future__ import annotations

from typing import Any
from uuid import UUID

from rest_framework import exceptions
from rest_framework.permissions import BasePermission

from contexts.authorization.services import (
    EffectiveAccess,
    resolve_effective_access,
)
from contexts.identity.auth_service import record_auth_event
from contexts.identity.models import (
    AuthenticationEventType,
    AuthenticationOutcome,
)


ACCESS_DENIED_MESSAGE = (
    "You do not have permission to perform this action."
)


class AuthorizationDenied(exceptions.PermissionDenied):
    """Stable authorization failure returned by protected internal APIs."""

    default_detail = ACCESS_DENIED_MESSAGE
    default_code = "authorization_denied"


def _identity_context(request: Any) -> tuple[UUID, UUID]:
    """
    Resolve the authenticated tenant and user-account identifiers.

    VridhiSessionAuthentication attaches vridhi_account and
    vridhi_membership to the request. Authorization never accepts a tenant or
    account identifier supplied by the request body, query string or headers.
    """

    membership = getattr(request, "vridhi_membership", None)
    account = getattr(request, "vridhi_account", None)

    tenant_id = getattr(membership, "tenant_id", None)
    user_account_id = getattr(account, "id", None)

    if tenant_id is None or user_account_id is None:
        raise AuthorizationDenied(
            "An authenticated Vridhi account and membership are required."
        )

    return tenant_id, user_account_id


def effective_access_for_request(request: Any) -> EffectiveAccess:
    """
    Resolve effective access once per request and cache it on the request.

    The resolver remains fail-closed: a user without an active AccessProfile
    receives an empty set of capabilities.
    """

    cached = getattr(request, "effective_access", None)

    if isinstance(cached, EffectiveAccess):
        return cached

    tenant_id, user_account_id = _identity_context(request)

    resolved = resolve_effective_access(
        tenant_id=tenant_id,
        user_account_id=user_account_id,
    )

    request.effective_access = resolved
    return resolved


def _record_denial(
    *,
    request: Any,
    access_code: str,
) -> None:
    """
    Record authorization denial without hiding audit persistence failures.

    Access-denial audit is security-relevant. The existing authentication audit
    model is reused so Phase 3B does not create a parallel audit subsystem.
    """

    account = getattr(request, "vridhi_account", None)
    membership = getattr(request, "vridhi_membership", None)

    if account is None or membership is None:
        return

    record_auth_event(
        request=request,
        event_type=AuthenticationEventType.ACCESS_DENIED,
        outcome=AuthenticationOutcome.DENIED,
        account=account,
        membership=membership,
        session=getattr(request, "auth", None),
        reason="RBAC_ACCESS_DENIED",
        metadata={
            "required_access": access_code,
            "request_method": str(getattr(request, "method", "")),
            "request_path": str(
                getattr(request, "path", "")
                or getattr(request, "path_info", "")
            ),
        },
    )


def require_access(
    request: Any,
    access_code: str,
) -> EffectiveAccess:
    """
    Require one capability inside a view or business action.

    Returns the resolved EffectiveAccess object so callers may also inspect
    department, team or service scope without resolving it again.
    """

    effective = effective_access_for_request(request)

    if effective.allows(access_code):
        return effective

    _record_denial(
        request=request,
        access_code=access_code,
    )

    raise AuthorizationDenied(
        f"{ACCESS_DENIED_MESSAGE} Required access: {access_code}."
    )


class HasAccess(BasePermission):
    """
    Reusable DRF permission base.

    Subclasses declare ``required_access``. Use ``access_permission()`` to
    construct a dedicated permission class without duplicating implementation.
    """

    required_access: str | None = None

    def has_permission(self, request: Any, view: Any) -> bool:
        access_code = (
            getattr(view, "required_access", None)
            or self.required_access
        )

        if not access_code:
            raise RuntimeError(
                "HasAccess requires a non-empty access capability code."
            )

        require_access(
            request,
            str(access_code),
        )

        return True


def access_permission(access_code: str) -> type[HasAccess]:
    """
    Return a DRF permission class bound to one access capability.

    Example:
        permission_classes = [
            IsAuthenticated,
            access_permission("clients.view"),
        ]
    """

    normalized = str(access_code).strip()

    if not normalized:
        raise ValueError("Access capability code cannot be empty.")

    class BoundAccessPermission(HasAccess):
        required_access = normalized

    safe_name = "".join(
        character if character.isalnum() else "_"
        for character in normalized
    )

    BoundAccessPermission.__name__ = (
        f"HasAccess_{safe_name}"
    )
    BoundAccessPermission.__qualname__ = (
        BoundAccessPermission.__name__
    )

    return BoundAccessPermission

class ActionAccessPermission(BasePermission):
    """
    Resolve a capability from the current DRF action.

    Existing header-principal requests remain available only when the explicit
    test/development compatibility setting is enabled. Production session
    requests always use the certified AccessProfile resolver.
    """

    action_access_map: dict[str, str] = {}

    def has_permission(self, request: Any, view: Any) -> bool:
        from django.conf import settings

        account = getattr(request, "vridhi_account", None)
        membership = getattr(request, "vridhi_membership", None)

        if account is None or membership is None:
            if bool(
                getattr(
                    settings,
                    "ALLOW_HEADER_PRINCIPAL_AUTH",
                    False,
                )
            ):
                return True

            raise AuthorizationDenied(
                "A session-authenticated Vridhi account is required."
            )

        action = str(getattr(view, "action", "") or "")
        access_code = self.action_access_map.get(action)

        if not access_code:
            raise RuntimeError(
                f"No access capability is configured for action: {action or 'unknown'}."
            )

        require_access(request, access_code)
        return True


class ClientAccessPermission(ActionAccessPermission):
    """Client and client-child CRUD authorization."""

    action_access_map = {
        "list": "clients.view",
        "retrieve": "clients.view",
        "create": "clients.create",
        "update": "clients.edit",
        "partial_update": "clients.edit",
        "destroy": "clients.delete",
    }

class WorkItemAccessPermission(ActionAccessPermission):
    """
    Simple WorkItem action-to-capability mapping.

    Uses only the approved Phase 3B catalogue. Existing owner, reviewer,
    workflow-state, QA and audit guards remain the final business controls.
    """

    action_access_map = {
        # Core work-item CRUD.
        "list": "work.view",
        "retrieve": "work.view",
        "health": "work.view",
        "history": "work.view",
        "create": "work.create",
        "update": "work.submit",
        "partial_update": "work.submit",

        # Deletion remains prohibited by the existing controller guard.
        # work.view allows that stable business denial to remain visible.
        "destroy": "work.view",

        # Existing owner-controlled execution and submission actions.
        "set_status": "work.submit",
        "submit_for_review": "work.submit",
        "prepare_qa": "work.submit",
        "save_preparer_checklist": "work.submit",
        "resolve_qa_issue_action": "work.submit",

        # Udyam post-review execution remains owner-controlled.
        # Service/process-position guards in WorkItemViewSet remain the
        # final business controls for these service-specific actions.
        "udyam_submit_application": "work.submit",
        "udyam_report_query": "work.submit",
        "udyam_resolve_query": "work.submit",
        "udyam_complete_registration": "work.submit",

        # Read-only QA information attached to a work item.
        "qa_readiness_action": "work.view",
        "qa_review_history_action": "work.view",

        # Existing reviewer-controlled actions.
        "save_reviewer_checklist": "quality.review",
        "raise_qa_issue_action": "quality.review",
        "approve": "work.approve",
        "return_for_rework": "work.approve",

        # Existing dedicated assignment action.
        "assign": "work.assign",

        # WorkItem-owned document generation uses the approved document
        # upload capability; document APIs themselves remain Phase 3B.5C.
        "generate_document_requests": "documents.upload",
    }

class DocumentRequestAccessPermission(ActionAccessPermission):
    """
    Authorization for document-request APIs.

    Existing contact, ownership, lifecycle, evidence and verification rules
    remain unchanged and execute after this capability check.
    """

    action_access_map = {
        "list": "documents.view",
        "retrieve": "documents.view",
        "attachments": "documents.view",

        "create": "documents.upload",
        "update": "documents.upload",
        "partial_update": "documents.upload",
        "upload": "documents.upload",

        "verify": "documents.review",

        # Deletion remains blocked by the existing controller rule.
        "destroy": "documents.view",
    }


class DocumentAttachmentAccessPermission(ActionAccessPermission):
    """
    Authorization for document-attachment APIs.

    Generic mutation and deletion remain prohibited by existing business
    guards. Review, duplicate resolution and canonical selection retain their
    existing reviewer and evidence rules.
    """

    action_access_map = {
        "list": "documents.view",
        "retrieve": "documents.view",
        "download": "documents.view",

        # Preserve the stable business denials for generic mutation.
        "create": "documents.view",
        "update": "documents.view",
        "partial_update": "documents.view",
        "destroy": "documents.view",

        "review": "documents.review",
        "resolve_duplicate": "documents.review",
        "mark_canonical": "documents.approve",
    }
