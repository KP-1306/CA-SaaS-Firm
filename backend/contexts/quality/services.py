from __future__ import annotations

from django.db import models, transaction
from django.utils import timezone

from contexts.identity.models import Employee

from .models import (
    QAChecklistStatus,
    QAIssueStatus,
    QAResponseValue,
    QAReviewCycle,
    QAReviewCycleStatus,
    QAReviewIssue,
    QAReviewResponse,
    ServiceQAChecklistItem,
    ServiceQAChecklistSet,
)


_ACTIVE_CYCLE_STATUSES = {
    QAReviewCycleStatus.PREPARATION,
    QAReviewCycleStatus.READY_FOR_REVIEW,
    QAReviewCycleStatus.IN_REVIEW,
    QAReviewCycleStatus.CHANGES_REQUESTED,
    QAReviewCycleStatus.RESUBMITTED,
}


def _actor_id(principal):
    return principal.principal_id


def _active_checklist(work_item):
    if not work_item.service_id:
        return None

    today = timezone.localdate()
    return (
        ServiceQAChecklistSet.objects.filter(
            tenant_id=work_item.tenant_id,
            service_id=work_item.service_id,
            status=QAChecklistStatus.ACTIVE,
        )
        .filter(
            models.Q(effective_from__isnull=True)
            | models.Q(effective_from__lte=today)
        )
        .filter(
            models.Q(effective_until__isnull=True)
            | models.Q(effective_until__gte=today)
        )
        .order_by("-version_number", "-effective_from", "-created_at")
        .first()
    )


def _latest_cycle(work_item):
    return (
        QAReviewCycle.objects.filter(
            tenant_id=work_item.tenant_id,
            work_item_id=work_item.id,
        )
        .order_by("-cycle_number", "-created_at")
        .first()
    )


def _principal_for_assignment(tenant_id, assignment_id):
    if not assignment_id:
        return None

    employee = Employee.objects.filter(
        tenant_id=tenant_id,
        id=assignment_id,
        is_active=True,
    ).first()
    if employee and employee.principal_id:
        return employee.principal_id
    return assignment_id


def _snapshot_item(item):
    return {
        "id": str(item.id),
        "code": item.code,
        "title": item.title,
        "description": item.description,
        "guidance": item.guidance,
        "display_order": item.display_order,
        "mandatory": item.mandatory,
        "preparer_required": item.preparer_required,
        "reviewer_required": item.reviewer_required,
        "evidence_required": item.evidence_required,
        "allow_not_applicable": item.allow_not_applicable,
    }


def cycle_summary(cycle):
    if cycle is None:
        return None

    responses = list(
        QAReviewResponse.objects.filter(
            tenant_id=cycle.tenant_id,
            review_cycle_id=cycle.id,
        ).order_by("checklist_item_code", "created_at")
    )
    issues = list(
        QAReviewIssue.objects.filter(
            tenant_id=cycle.tenant_id,
            review_cycle_id=cycle.id,
        ).order_by("-created_at")
    )

    return {
        "id": str(cycle.id),
        "work_item_id": str(cycle.work_item_id),
        "service_id": str(cycle.service_id) if cycle.service_id else None,
        "checklist_set_id": (
            str(cycle.checklist_set_id) if cycle.checklist_set_id else None
        ),
        "checklist_version": cycle.checklist_version,
        "cycle_number": cycle.cycle_number,
        "status": cycle.status,
        "owner_user_id": (
            str(cycle.owner_user_id) if cycle.owner_user_id else None
        ),
        "reviewer_user_id": (
            str(cycle.reviewer_user_id) if cycle.reviewer_user_id else None
        ),
        "submitted_at": cycle.submitted_at,
        "review_started_at": cycle.review_started_at,
        "changes_requested_at": cycle.changes_requested_at,
        "resubmitted_at": cycle.resubmitted_at,
        "approved_at": cycle.approved_at,
        "submission_comment": cycle.submission_comment,
        "review_comment": cycle.review_comment,
        "approval_comment": cycle.approval_comment,
        "responses": [
            {
                "id": str(response.id),
                "checklist_item_id": (
                    str(response.checklist_item_id)
                    if response.checklist_item_id
                    else None
                ),
                "code": response.checklist_item_code,
                "title": response.checklist_item_title,
                "mandatory": response.mandatory,
                "preparer_response": response.preparer_response,
                "preparer_comment": response.preparer_comment,
                "preparer_evidence_attachment_id": (
                    str(response.preparer_evidence_attachment_id)
                    if response.preparer_evidence_attachment_id
                    else None
                ),
                "reviewer_response": response.reviewer_response,
                "reviewer_comment": response.reviewer_comment,
                "reviewer_evidence_attachment_id": (
                    str(response.reviewer_evidence_attachment_id)
                    if response.reviewer_evidence_attachment_id
                    else None
                ),
            }
            for response in responses
        ],
        "issues": [
            {
                "id": str(issue.id),
                "response_id": str(issue.response_id) if issue.response_id else None,
                "document_request_id": (
                    str(issue.document_request_id)
                    if issue.document_request_id
                    else None
                ),
                "attachment_id": (
                    str(issue.attachment_id) if issue.attachment_id else None
                ),
                "category": issue.category,
                "severity": issue.severity,
                "status": issue.status,
                "title": issue.title,
                "description": issue.description,
                "assigned_to": (
                    str(issue.assigned_to) if issue.assigned_to else None
                ),
                "due_date": issue.due_date,
                "resolution_comment": issue.resolution_comment,
            }
            for issue in issues
        ],
    }


@transaction.atomic
def prepare_cycle(work_item, principal):
    checklist = _active_checklist(work_item)
    if checklist is None:
        return None

    latest = _latest_cycle(work_item)
    if latest and latest.status in _ACTIVE_CYCLE_STATUSES:
        return latest

    next_number = 1 if latest is None else latest.cycle_number + 1
    items = list(
        ServiceQAChecklistItem.objects.filter(
            tenant_id=work_item.tenant_id,
            checklist_set_id=checklist.id,
            service_id=work_item.service_id,
            is_active=True,
        ).order_by("display_order", "title", "id")
    )

    actor = _actor_id(principal)
    cycle = QAReviewCycle.objects.create(
        tenant_id=work_item.tenant_id,
        created_by=actor,
        updated_by=actor,
        work_item_id=work_item.id,
        service_id=work_item.service_id,
        checklist_set_id=checklist.id,
        checklist_version=checklist.version_number,
        cycle_number=next_number,
        status=QAReviewCycleStatus.PREPARATION,
        owner_user_id=work_item.owner_user_id,
        reviewer_user_id=work_item.reviewer_user_id,
        checklist_snapshot=[_snapshot_item(item) for item in items],
    )

    QAReviewResponse.objects.bulk_create(
        [
            QAReviewResponse(
                tenant_id=work_item.tenant_id,
                created_by=actor,
                updated_by=actor,
                review_cycle_id=cycle.id,
                work_item_id=work_item.id,
                checklist_item_id=item.id,
                checklist_item_code=item.code,
                checklist_item_title=item.title,
                mandatory=item.mandatory,
            )
            for item in items
        ]
    )
    return cycle


def _snapshot_by_code(cycle):
    return {
        row["code"]: row
        for row in (cycle.checklist_snapshot or [])
        if row.get("code")
    }


def qa_readiness(work_item):
    checklist = _active_checklist(work_item)
    if checklist is None:
        return {
            "enabled": False,
            "ready_for_submission": True,
            "ready_for_approval": True,
            "blockers": [],
            "cycle": None,
        }

    cycle = _latest_cycle(work_item)
    if cycle is None:
        return {
            "enabled": True,
            "ready_for_submission": False,
            "ready_for_approval": False,
            "blockers": [
                {
                    "code": "QA_CYCLE_REQUIRED",
                    "detail": "Prepare the QA checklist before submission.",
                }
            ],
            "cycle": None,
        }

    snapshots = _snapshot_by_code(cycle)
    responses = list(
        QAReviewResponse.objects.filter(
            tenant_id=work_item.tenant_id,
            review_cycle_id=cycle.id,
        )
    )
    submission_blockers = []
    approval_blockers = []

    for response in responses:
        snapshot = snapshots.get(response.checklist_item_code, {})
        allow_na = bool(snapshot.get("allow_not_applicable"))
        prep_allowed = {QAResponseValue.YES}
        review_allowed = {QAResponseValue.YES}
        if allow_na:
            prep_allowed.add(QAResponseValue.NOT_APPLICABLE)
            review_allowed.add(QAResponseValue.NOT_APPLICABLE)

        if snapshot.get("preparer_required") and response.preparer_response not in prep_allowed:
            submission_blockers.append(
                {
                    "code": "PREPARER_CHECK_PENDING",
                    "response_id": str(response.id),
                    "item_code": response.checklist_item_code,
                    "detail": f"Complete preparer check: {response.checklist_item_title}.",
                }
            )

        if (
            snapshot.get("preparer_required")
            and snapshot.get("evidence_required")
            and response.preparer_response == QAResponseValue.YES
            and not response.preparer_evidence_attachment_id
        ):
            submission_blockers.append(
                {
                    "code": "PREPARER_EVIDENCE_REQUIRED",
                    "response_id": str(response.id),
                    "item_code": response.checklist_item_code,
                    "detail": f"Attach evidence for: {response.checklist_item_title}.",
                }
            )

        if snapshot.get("reviewer_required") and response.reviewer_response not in review_allowed:
            approval_blockers.append(
                {
                    "code": "REVIEWER_CHECK_PENDING",
                    "response_id": str(response.id),
                    "item_code": response.checklist_item_code,
                    "detail": f"Complete reviewer check: {response.checklist_item_title}.",
                }
            )

        if (
            snapshot.get("reviewer_required")
            and snapshot.get("evidence_required")
            and response.reviewer_response == QAResponseValue.YES
            and not response.reviewer_evidence_attachment_id
        ):
            approval_blockers.append(
                {
                    "code": "REVIEWER_EVIDENCE_REQUIRED",
                    "response_id": str(response.id),
                    "item_code": response.checklist_item_code,
                    "detail": f"Attach reviewer evidence for: {response.checklist_item_title}.",
                }
            )

    owner_principal = _principal_for_assignment(
        work_item.tenant_id,
        work_item.owner_user_id,
    )
    reviewer_principal = _principal_for_assignment(
        work_item.tenant_id,
        work_item.reviewer_user_id,
    )
    if (
        checklist.prevent_self_review
        and owner_principal
        and reviewer_principal
        and owner_principal == reviewer_principal
    ):
        submission_blockers.append(
            {
                "code": "SELF_REVIEW_BLOCKED",
                "detail": "The preparer and reviewer must be different people.",
            }
        )

    open_issues = list(
        QAReviewIssue.objects.filter(
            tenant_id=work_item.tenant_id,
            review_cycle_id=cycle.id,
            status__in=[QAIssueStatus.OPEN, QAIssueStatus.REOPENED],
        ).values_list("id", "title")
    )
    for issue_id, title in open_issues:
        approval_blockers.append(
            {
                "code": "OPEN_QA_ISSUE",
                "issue_id": str(issue_id),
                "detail": f"Resolve QA issue: {title}.",
            }
        )

    return {
        "enabled": True,
        "ready_for_submission": not submission_blockers,
        "ready_for_approval": not approval_blockers,
        "submission_blockers": submission_blockers,
        "approval_blockers": approval_blockers,
        "blockers": submission_blockers + approval_blockers,
        "cycle": cycle_summary(cycle),
    }


@transaction.atomic
def save_responses(work_item, principal, payload, *, role):
    cycle = prepare_cycle(work_item, principal)
    if cycle is None:
        raise ValueError("No active QA checklist is configured for this service.")

    if role == "preparer":
        allowed_statuses = {
            QAReviewCycleStatus.PREPARATION,
            QAReviewCycleStatus.CHANGES_REQUESTED,
            QAReviewCycleStatus.RESUBMITTED,
        }
    else:
        allowed_statuses = {
            QAReviewCycleStatus.READY_FOR_REVIEW,
            QAReviewCycleStatus.IN_REVIEW,
            QAReviewCycleStatus.RESUBMITTED,
        }

    if cycle.status not in allowed_statuses:
        raise ValueError(f"Checklist responses cannot be changed while cycle is {cycle.status}.")

    rows = payload.get("responses") if isinstance(payload, dict) else None
    if not isinstance(rows, list) or not rows:
        raise ValueError("Provide a non-empty responses list.")

    snapshot = _snapshot_by_code(cycle)
    response_map = {
        str(row.id): row
        for row in QAReviewResponse.objects.filter(
            tenant_id=work_item.tenant_id,
            review_cycle_id=cycle.id,
        )
    }
    valid_values = {choice for choice, _ in QAResponseValue.choices}
    actor = _actor_id(principal)
    now = timezone.now()

    for incoming in rows:
        response = response_map.get(str(incoming.get("id") or ""))
        if response is None:
            raise ValueError("A response does not belong to this QA cycle.")

        value = incoming.get("value")
        if value not in valid_values:
            raise ValueError(f"Invalid QA response value: {value}.")

        item_snapshot = snapshot.get(response.checklist_item_code, {})
        if value == QAResponseValue.NOT_APPLICABLE and not item_snapshot.get(
            "allow_not_applicable"
        ):
            raise ValueError(
                f"Not applicable is not allowed for {response.checklist_item_title}."
            )

        comment = str(incoming.get("comment") or "").strip()
        evidence = incoming.get("evidence_attachment_id") or None

        if role == "preparer":
            response.preparer_response = value
            response.preparer_comment = comment
            response.preparer_evidence_attachment_id = evidence
            response.preparer_completed_by = actor
            response.preparer_completed_at = now
            fields = [
                "preparer_response",
                "preparer_comment",
                "preparer_evidence_attachment_id",
                "preparer_completed_by",
                "preparer_completed_at",
            ]
        else:
            response.reviewer_response = value
            response.reviewer_comment = comment
            response.reviewer_evidence_attachment_id = evidence
            response.reviewer_completed_by = actor
            response.reviewer_completed_at = now
            fields = [
                "reviewer_response",
                "reviewer_comment",
                "reviewer_evidence_attachment_id",
                "reviewer_completed_by",
                "reviewer_completed_at",
            ]

        response.updated_by = actor
        response.save(update_fields=[*fields, "updated_by", "row_version"])

    if role == "reviewer" and cycle.status == QAReviewCycleStatus.READY_FOR_REVIEW:
        cycle.status = QAReviewCycleStatus.IN_REVIEW
        cycle.review_started_at = cycle.review_started_at or now
        cycle.updated_by = actor
        cycle.save(
            update_fields=[
                "status",
                "review_started_at",
                "updated_by",
                "row_version",
            ]
        )

    return cycle


@transaction.atomic
def mark_submitted(work_item, principal, comment=""):
    cycle = prepare_cycle(work_item, principal)
    if cycle is None:
        return None

    readiness = qa_readiness(work_item)
    if not readiness["ready_for_submission"]:
        raise ValueError("QA preparer checklist is incomplete.")

    now = timezone.now()
    was_rework = cycle.status in {
        QAReviewCycleStatus.CHANGES_REQUESTED,
        QAReviewCycleStatus.RESUBMITTED,
    }
    cycle.status = (
        QAReviewCycleStatus.RESUBMITTED
        if was_rework
        else QAReviewCycleStatus.READY_FOR_REVIEW
    )
    cycle.submitted_at = cycle.submitted_at or now
    if was_rework:
        cycle.resubmitted_at = now
    cycle.submission_comment = str(comment or "").strip()
    cycle.owner_user_id = work_item.owner_user_id
    cycle.reviewer_user_id = work_item.reviewer_user_id
    cycle.updated_by = _actor_id(principal)
    cycle.save(
        update_fields=[
            "status",
            "submitted_at",
            "resubmitted_at",
            "submission_comment",
            "owner_user_id",
            "reviewer_user_id",
            "updated_by",
            "row_version",
        ]
    )
    return cycle


@transaction.atomic
def mark_changes_requested(work_item, principal, comment):
    cycle = _latest_cycle(work_item)
    if cycle is None or cycle.checklist_set_id is None:
        return None

    cycle.status = QAReviewCycleStatus.CHANGES_REQUESTED
    cycle.changes_requested_at = timezone.now()
    cycle.review_comment = str(comment or "").strip()
    cycle.updated_by = _actor_id(principal)
    cycle.save(
        update_fields=[
            "status",
            "changes_requested_at",
            "review_comment",
            "updated_by",
            "row_version",
        ]
    )
    return cycle


@transaction.atomic
def mark_approved(work_item, principal, comment=""):
    checklist = _active_checklist(work_item)
    if checklist is None:
        return None

    cycle = _latest_cycle(work_item)
    if cycle is None:
        raise ValueError("Prepare and complete the QA review before approval.")

    readiness = qa_readiness(work_item)
    if not readiness["ready_for_approval"]:
        raise ValueError("QA reviewer checklist or issues are incomplete.")

    cycle.status = QAReviewCycleStatus.APPROVED
    cycle.approved_at = timezone.now()
    cycle.approval_comment = str(comment or "").strip()
    cycle.updated_by = _actor_id(principal)
    cycle.save(
        update_fields=[
            "status",
            "approved_at",
            "approval_comment",
            "updated_by",
            "row_version",
        ]
    )
    return cycle


@transaction.atomic
def raise_issue(work_item, principal, payload):
    cycle = _latest_cycle(work_item)
    if cycle is None:
        raise ValueError("No QA review cycle exists for this work item.")

    title = str(payload.get("title") or "").strip()
    description = str(payload.get("description") or "").strip()
    if not title or not description:
        raise ValueError("QA issue title and description are required.")

    actor = _actor_id(principal)
    return QAReviewIssue.objects.create(
        tenant_id=work_item.tenant_id,
        created_by=actor,
        updated_by=actor,
        review_cycle_id=cycle.id,
        work_item_id=work_item.id,
        response_id=payload.get("response_id") or None,
        document_request_id=payload.get("document_request_id") or None,
        attachment_id=payload.get("attachment_id") or None,
        category=str(payload.get("category") or "").strip(),
        severity=payload.get("severity") or "MEDIUM",
        title=title,
        description=description,
        raised_by=actor,
        assigned_to=payload.get("assigned_to") or work_item.owner_user_id,
        due_date=payload.get("due_date") or None,
    )


@transaction.atomic
def resolve_issue(work_item, principal, issue_id, comment):
    issue = QAReviewIssue.objects.filter(
        tenant_id=work_item.tenant_id,
        work_item_id=work_item.id,
        id=issue_id,
    ).first()
    if issue is None:
        raise ValueError("QA issue was not found for this work item.")
    if issue.status not in {QAIssueStatus.OPEN, QAIssueStatus.REOPENED}:
        raise ValueError("Only an open QA issue can be resolved.")

    resolution_comment = str(comment or "").strip()
    if not resolution_comment:
        raise ValueError("A resolution comment is required.")

    actor = _actor_id(principal)
    issue.status = QAIssueStatus.RESOLVED
    issue.resolution_comment = resolution_comment
    issue.resolved_by = actor
    issue.resolved_at = timezone.now()
    issue.updated_by = actor
    issue.save(
        update_fields=[
            "status",
            "resolution_comment",
            "resolved_by",
            "resolved_at",
            "updated_by",
            "row_version",
        ]
    )
    return issue


def review_history(work_item):
    return [
        cycle_summary(cycle)
        for cycle in QAReviewCycle.objects.filter(
            tenant_id=work_item.tenant_id,
            work_item_id=work_item.id,
        ).order_by("-cycle_number", "-created_at")
    ]
