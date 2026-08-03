from __future__ import annotations

from datetime import date
from typing import Any

from .models import (
    DocumentRequest,
    DocumentRequestStatus,
)


def request_dependency_status(
    document_request: DocumentRequest,
) -> dict[str, Any]:
    """Evaluate one document request as a workflow dependency."""

    expired = bool(
        document_request.expires_on
        and document_request.expires_on < date.today()
    )

    if document_request.status == DocumentRequestStatus.WAIVED:
        satisfied = True
        reason = "WAIVED"

    elif document_request.status == DocumentRequestStatus.ACCEPTED:
        satisfied = not expired
        reason = "EXPIRED" if expired else "SATISFIED"

    elif expired:
        satisfied = False
        reason = "EXPIRED"

    elif document_request.status == DocumentRequestStatus.REJECTED:
        satisfied = False
        reason = "REJECTED"

    elif document_request.status == DocumentRequestStatus.REQUESTED:
        satisfied = False
        reason = "NOT_RECEIVED"

    elif (
        document_request.status
        == DocumentRequestStatus.PARTIALLY_RECEIVED
    ):
        satisfied = False
        reason = "PARTIALLY_RECEIVED"

    elif document_request.status == DocumentRequestStatus.RECEIVED:
        satisfied = False
        reason = "PENDING_ACCEPTANCE"

    else:
        satisfied = False
        reason = str(document_request.status or "UNKNOWN")

    return {
        "id": str(document_request.id),
        "name": document_request.name,
        "category": document_request.category,
        "mandatory": document_request.mandatory,
        "status": document_request.status,
        "due_date": (
            document_request.due_date.isoformat()
            if document_request.due_date
            else None
        ),
        "expires_on": (
            document_request.expires_on.isoformat()
            if document_request.expires_on
            else None
        ),
        "auto_generated": document_request.auto_generated,
        "source_requirement_id": (
            str(document_request.source_requirement_id)
            if document_request.source_requirement_id
            else None
        ),
        "is_expired": expired,
        "satisfied": satisfied,
        "reason": reason,
    }


def calculate_document_readiness(work_item) -> dict[str, Any]:
    """Calculate document completeness and workflow blockers."""

    requests = list(
        DocumentRequest.objects.filter(
            tenant_id=work_item.tenant_id,
            work_item_id=work_item.id,
        ).order_by(
            "-mandatory",
            "due_date",
            "name",
            "id",
        )
    )

    documents = [
        request_dependency_status(document_request)
        for document_request in requests
    ]

    mandatory = [
        row
        for row in documents
        if row["mandatory"]
    ]

    optional = [
        row
        for row in documents
        if not row["mandatory"]
    ]

    satisfied = [
        row
        for row in documents
        if row["satisfied"]
    ]

    mandatory_satisfied = [
        row
        for row in mandatory
        if row["satisfied"]
    ]

    blockers = [
        row
        for row in mandatory
        if not row["satisfied"]
    ]

    expired = [
        row
        for row in documents
        if row["is_expired"]
        and row["reason"] != "WAIVED"
    ]

    rejected = [
        row
        for row in documents
        if row["reason"] == "REJECTED"
    ]

    pending_acceptance = [
        row
        for row in documents
        if row["reason"] == "PENDING_ACCEPTANCE"
    ]

    total = len(documents)

    health_score = (
        round((len(satisfied) / total) * 100)
        if total
        else 100
    )

    mandatory_score = (
        round(
            (
                len(mandatory_satisfied)
                / len(mandatory)
            )
            * 100
        )
        if mandatory
        else 100
    )

    ready = len(blockers) == 0

    if ready:
        readiness_state = "READY"

    elif any(
        row["reason"] == "EXPIRED"
        for row in blockers
    ):
        readiness_state = "BLOCKED_BY_EXPIRED_DOCUMENT"

    elif any(
        row["reason"] == "REJECTED"
        for row in blockers
    ):
        readiness_state = "BLOCKED_BY_REJECTED_DOCUMENT"

    elif any(
        row["reason"] == "PENDING_ACCEPTANCE"
        for row in blockers
    ):
        readiness_state = "BLOCKED_PENDING_ACCEPTANCE"

    elif any(
        row["reason"] == "PARTIALLY_RECEIVED"
        for row in blockers
    ):
        readiness_state = "BLOCKED_PARTIALLY_RECEIVED"

    else:
        readiness_state = "WAITING_FOR_CLIENT"

    return {
        "work_item_id": str(work_item.id),
        "ready_for_review": ready,
        "readiness_state": readiness_state,
        "health_score": health_score,
        "mandatory_score": mandatory_score,
        "total_documents": total,
        "satisfied_documents": len(satisfied),
        "pending_documents": total - len(satisfied),
        "mandatory_total": len(mandatory),
        "mandatory_satisfied": len(mandatory_satisfied),
        "mandatory_missing": len(blockers),
        "optional_total": len(optional),
        "expired_count": len(expired),
        "rejected_count": len(rejected),
        "pending_acceptance_count": len(pending_acceptance),
        "blockers": blockers,
        "documents": documents,
    }
