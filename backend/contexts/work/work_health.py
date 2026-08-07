from __future__ import annotations

from datetime import date

from django.utils import timezone

from contexts.configuration.models import ServiceOperationalField

from .document_intelligence import calculate_document_readiness
from .models import (
    DocumentRequest,
    DocumentRequestStatus,
    WorkNote,
    WorkStatus,
)


TERMINAL_STATUSES = {
    WorkStatus.COMPLETED,
    WorkStatus.CANCELLED,
}


def _value_present(value) -> bool:
    """Treat only genuinely supplied operational values as complete."""

    if value is None:
        return False

    if isinstance(value, str):
        return bool(value.strip())

    if isinstance(value, (list, tuple, dict, set)):
        return bool(value)

    # False and numeric zero are valid entered values.
    return True


def _operational_health(work_item) -> dict:
    if not work_item.service_id:
        return {
            "total": 0,
            "completed": 0,
            "remaining": 0,
            "mandatory_total": 0,
            "mandatory_completed": 0,
            "mandatory_remaining": 0,
            "completion_percent": None,
        }

    definitions = list(
        ServiceOperationalField.objects.filter(
            tenant_id=work_item.tenant_id,
            service_id=work_item.service_id,
            is_active=True,
        ).order_by(
            "display_order",
            "key",
        )
    )

    data = (
        work_item.operational_data
        if isinstance(work_item.operational_data, dict)
        else {}
    )

    completed = [
        field
        for field in definitions
        if _value_present(data.get(field.key))
    ]

    mandatory = [
        field
        for field in definitions
        if field.required
    ]

    mandatory_completed = [
        field
        for field in mandatory
        if _value_present(data.get(field.key))
    ]

    total = len(definitions)
    completed_count = len(completed)

    return {
        "total": total,
        "completed": completed_count,
        "remaining": total - completed_count,
        "mandatory_total": len(mandatory),
        "mandatory_completed": len(mandatory_completed),
        "mandatory_remaining": (
            len(mandatory) - len(mandatory_completed)
        ),
        "completion_percent": (
            round((completed_count / total) * 100)
            if total
            else None
        ),
    }


def _document_health(work_item) -> dict:
    readiness = calculate_document_readiness(work_item)

    rows = list(
        DocumentRequest.objects.filter(
            tenant_id=work_item.tenant_id,
            work_item_id=work_item.id,
        )
    )

    missing = 0
    pending_review = 0
    rejected = 0

    for row in rows:
        if row.status == DocumentRequestStatus.REQUESTED:
            missing += 1

        elif row.status == DocumentRequestStatus.PARTIALLY_RECEIVED:
            pending_review += 1

        elif row.status == DocumentRequestStatus.REJECTED:
            rejected += 1

    return {
        "total": readiness["total_documents"],
        "satisfied": readiness["satisfied_documents"],
        "pending": readiness["pending_documents"],
        "mandatory_total": readiness["mandatory_total"],
        "mandatory_satisfied": (
            readiness["mandatory_satisfied"]
        ),
        "mandatory_missing": readiness["mandatory_missing"],
        "missing": missing,
        "pending_review": pending_review,
        "rejected": max(
            rejected,
            readiness["rejected_count"],
        ),
        "expired": readiness["expired_count"],
        "pending_acceptance": (
            readiness["pending_acceptance_count"]
        ),
        "ready_for_review": readiness["ready_for_review"],
        "readiness_state": readiness["readiness_state"],
        "health_score": readiness["health_score"],
        "blockers": readiness["blockers"],
    }


def _due_health(work_item, today: date) -> dict:
    if (
        not work_item.due_date
        or work_item.status in TERMINAL_STATUSES
    ):
        return {
            "state": "ON_TRACK",
            "days_to_due": None,
        }

    days = (work_item.due_date - today).days

    if days < 0:
        state = "OVERDUE"
    elif days <= 3:
        state = "DUE_SOON"
    else:
        state = "ON_TRACK"

    return {
        "state": state,
        "days_to_due": days,
    }


def _waiting_since(work_item):
    if work_item.status == WorkStatus.WAITING_FOR_CLIENT:
        note = (
            WorkNote.objects.filter(
                tenant_id=work_item.tenant_id,
                work_item_id=work_item.id,
                to_status=WorkStatus.WAITING_FOR_CLIENT,
            )
            .order_by("-created_at")
            .first()
        )

        if note:
            return note.created_at

    if (
        work_item.status == WorkStatus.READY_FOR_REVIEW
        and work_item.submitted_for_review_at
    ):
        return work_item.submitted_for_review_at

    return work_item.updated_at or work_item.created_at


def _waiting_health(work_item, now) -> dict:
    if work_item.status in TERMINAL_STATUSES:
        return {
            "waiting_days": 0,
            "waiting_since": None,
        }

    started = _waiting_since(work_item)

    if not started:
        return {
            "waiting_days": 0,
            "waiting_since": None,
        }

    elapsed = now - started

    return {
        "waiting_days": max(elapsed.days, 0),
        "waiting_since": started.isoformat(),
    }


def _current_controller(work_item) -> str:
    if work_item.status == WorkStatus.WAITING_FOR_CLIENT:
        return "CLIENT"

    if work_item.status == WorkStatus.READY_FOR_REVIEW:
        return "REVIEWER"

    if work_item.status in TERMINAL_STATUSES:
        return "NONE"

    return "OWNER"


def _review_percent(status: str) -> int:
    if status == WorkStatus.COMPLETED:
        return 100

    if status == WorkStatus.READY_FOR_REVIEW:
        return 50

    if status == WorkStatus.REWORK_REQUIRED:
        return 25

    return 0


def _progress(
    work_item,
    operational: dict,
    documents: dict,
) -> int:
    components = []

    # Only configured dimensions participate in the denominator.
    if operational["total"]:
        components.append(
            (
                40,
                operational["completion_percent"],
            )
        )

    if documents["total"]:
        document_percent = round(
            (
                documents["satisfied"]
                / documents["total"]
            )
            * 100
        )

        components.append(
            (
                30,
                document_percent,
            )
        )

    # Lifecycle dimensions always apply.
    components.append(
        (
            20,
            _review_percent(work_item.status),
        )
    )

    components.append(
        (
            10,
            (
                100
                if work_item.status == WorkStatus.COMPLETED
                else 0
            ),
        )
    )

    weight_total = sum(weight for weight, _value in components)

    if not weight_total:
        return 0

    weighted = sum(
        weight * value
        for weight, value in components
    )

    return max(
        0,
        min(
            100,
            round(weighted / weight_total),
        ),
    )


def _risk_and_health(
    work_item,
    *,
    due: dict,
    waiting: dict,
    operational: dict,
    documents: dict,
) -> tuple[str, str, list[str]]:
    reasons = []

    if work_item.status == WorkStatus.COMPLETED:
        return (
            "LOW",
            "GREEN",
            ["Work is completed."],
        )

    if work_item.status == WorkStatus.CANCELLED:
        return (
            "LOW",
            "GREEN",
            ["Work is cancelled and requires no further action."],
        )

    high_risk = False
    medium_risk = False

    if due["state"] == "OVERDUE":
        high_risk = True
        reasons.append("Work is overdue.")

    if documents["expired"]:
        high_risk = True
        reasons.append(
            f"{documents['expired']} document dependency "
            "is expired."
        )

    if documents["rejected"]:
        high_risk = True
        reasons.append(
            f"{documents['rejected']} document dependency "
            "is rejected."
        )

    if (
        waiting["waiting_days"] >= 10
        and _current_controller(work_item)
        in {"CLIENT", "REVIEWER"}
    ):
        high_risk = True
        reasons.append(
            f"Work has been waiting for "
            f"{waiting['waiting_days']} days."
        )

    if (
        str(work_item.priority) == "URGENT"
        and (
            operational["mandatory_remaining"]
            or documents["mandatory_missing"]
        )
    ):
        high_risk = True
        reasons.append(
            "Urgent work still has mandatory dependencies."
        )

    if due["state"] == "DUE_SOON":
        medium_risk = True
        reasons.append("Work is due within 3 days.")

    if operational["mandatory_remaining"]:
        medium_risk = True
        reasons.append(
            f"{operational['mandatory_remaining']} mandatory "
            "operational field(s) remain."
        )

    if documents["mandatory_missing"]:
        medium_risk = True
        reasons.append(
            f"{documents['mandatory_missing']} mandatory "
            "document dependency/dependencies remain."
        )

    if documents["pending_review"]:
        medium_risk = True
        reasons.append(
            f"{documents['pending_review']} document(s) "
            "are pending review."
        )

    if (
        waiting["waiting_days"] >= 5
        and _current_controller(work_item)
        in {"CLIENT", "REVIEWER"}
    ):
        medium_risk = True
        reasons.append(
            f"Work has been waiting for "
            f"{waiting['waiting_days']} days."
        )

    if str(work_item.priority) in {"HIGH", "URGENT"}:
        medium_risk = True

    if high_risk:
        return "HIGH", "RED", reasons

    if medium_risk:
        return "MEDIUM", "AMBER", reasons

    if not reasons:
        reasons.append(
            "No material operational risk detected."
        )

    return "LOW", "GREEN", reasons


def _next_action(
    work_item,
    operational: dict,
    documents: dict,
) -> dict:
    if work_item.status == WorkStatus.COMPLETED:
        return {
            "code": "NONE",
            "label": "Work completed",
        }

    if work_item.status == WorkStatus.CANCELLED:
        return {
            "code": "NONE",
            "label": "Work cancelled",
        }

    if work_item.status == WorkStatus.READY_FOR_REVIEW:
        return {
            "code": "REVIEW_WORK",
            "label": "Review submitted work",
        }

    if work_item.status == WorkStatus.REWORK_REQUIRED:
        return {
            "code": "RESUME_REWORK",
            "label": "Resume rework",
        }

    if work_item.status == WorkStatus.WAITING_FOR_CLIENT:
        return {
            "code": "AWAIT_CLIENT_DOCUMENTS",
            "label": "Await client documents",
        }

    if operational["mandatory_remaining"]:
        return {
            "code": "COMPLETE_REQUIRED_FIELDS",
            "label": "Complete required work details",
        }

    if documents["missing"] or documents["mandatory_missing"]:
        return {
            "code": "REQUEST_MISSING_DOCUMENTS",
            "label": "Request missing client documents",
        }

    if (
        documents["pending_review"]
        or documents["pending_acceptance"]
    ):
        return {
            "code": "REVIEW_DOCUMENTS",
            "label": "Review received documents",
        }

    if (
        work_item.status == WorkStatus.NOT_STARTED
    ):
        return {
            "code": "START_WORK",
            "label": "Start work",
        }

    if (
        work_item.status == WorkStatus.IN_PROGRESS
        and documents["ready_for_review"]
    ):
        return {
            "code": "SUBMIT_FOR_REVIEW",
            "label": "Submit work for review",
        }

    return {
        "code": "CONTINUE_WORK",
        "label": "Continue work",
    }


def calculate_work_health(
    work_item,
    *,
    now=None,
) -> dict:
    """Return the canonical non-persisted Work Health Snapshot."""

    now = now or timezone.now()
    today = now.date()

    operational = _operational_health(work_item)
    documents = _document_health(work_item)
    due = _due_health(work_item, today)
    waiting = _waiting_health(work_item, now)

    risk, health, reasons = _risk_and_health(
        work_item,
        due=due,
        waiting=waiting,
        operational=operational,
        documents=documents,
    )

    progress = _progress(
        work_item,
        operational,
        documents,
    )

    return {
        "contract_version": 1,
        "work_item_id": str(work_item.id),
        "progress": progress,
        "health": health,
        "risk": risk,
        "current_controller": _current_controller(work_item),
        "waiting_days": waiting["waiting_days"],
        "waiting_since": waiting["waiting_since"],
        "due_state": due["state"],
        "days_to_due": due["days_to_due"],
        "operational": operational,
        "documents": documents,
        "next_action": _next_action(
            work_item,
            operational,
            documents,
        ),
        "reasons": reasons,
        "calculated_at": now.isoformat(),
    }
