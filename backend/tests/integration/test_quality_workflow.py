from __future__ import annotations

import uuid

import pytest
from django.test import Client as HttpClient

from contexts.identity.models import Employee
from contexts.quality.models import (
    QAChecklistStatus,
    QAIssueStatus,
    QAReviewCycle,
    QAReviewCycleStatus,
    QAReviewIssue,
    ServiceQAChecklistItem,
    ServiceQAChecklistSet,
)
from contexts.work.models import WorkItem, WorkStatus


TENANT = uuid.UUID("11111111-1111-1111-1111-111111111111")
OWNER = uuid.UUID("22222222-2222-2222-2222-222222222222")
REVIEWER = uuid.UUID("44444444-4444-4444-4444-444444444444")


def _headers(principal=OWNER):
    return {
        "HTTP_X_TENANT_ID": str(TENANT),
        "HTTP_X_PRINCIPAL_ID": str(principal),
    }


def _setup_work(*, reviewer_principal=REVIEWER):
    service_id = uuid.uuid4()
    reviewer = Employee.objects.create(
        tenant_id=TENANT,
        created_by=OWNER,
        updated_by=OWNER,
        name="QA Reviewer",
        email=f"qa-{reviewer_principal}@example.com",
        principal_id=reviewer_principal,
        is_active=True,
    )
    work = WorkItem.objects.create(
        tenant_id=TENANT,
        created_by=OWNER,
        updated_by=OWNER,
        title="GST Return QA",
        client_id=uuid.uuid4(),
        service_id=service_id,
        owner_user_id=OWNER,
        reviewer_user_id=reviewer.id,
        status=WorkStatus.IN_PROGRESS,
    )
    checklist = ServiceQAChecklistSet.objects.create(
        tenant_id=TENANT,
        created_by=OWNER,
        updated_by=OWNER,
        service_id=service_id,
        name="GST QA",
        version_number=1,
        status=QAChecklistStatus.ACTIVE,
        prevent_self_review=True,
    )
    ServiceQAChecklistItem.objects.create(
        tenant_id=TENANT,
        created_by=OWNER,
        updated_by=OWNER,
        checklist_set_id=checklist.id,
        service_id=service_id,
        code="GST-001",
        title="Verify reconciliation",
        mandatory=True,
        preparer_required=True,
        reviewer_required=True,
    )
    return work


def _prepare(http, work):
    response = http.post(
        f"/api/v1/work-items/{work.id}/prepare-qa/",
        data={},
        content_type="application/json",
        **_headers(),
    )
    assert response.status_code == 200, response.content
    return response.json()["cycle"]


def _save_preparer(http, work, response_id):
    response = http.post(
        f"/api/v1/work-items/{work.id}/save-preparer-checklist/",
        data={"responses": [{"id": response_id, "value": "YES"}]},
        content_type="application/json",
        **_headers(),
    )
    assert response.status_code == 200, response.content


def _submit(http, work):
    return http.post(
        f"/api/v1/work-items/{work.id}/submit_for_review/",
        data={},
        content_type="application/json",
        **_headers(),
    )


@pytest.mark.django_db
def test_qa_checklist_blocks_submission_then_approval_until_completed():
    http = HttpClient()
    work = _setup_work()
    cycle = _prepare(http, work)
    response_id = cycle["responses"][0]["id"]

    blocked = _submit(http, work)
    assert blocked.status_code == 400
    assert blocked.json()["code"] == "QA_CHECKLIST_BLOCKED"

    _save_preparer(http, work, response_id)
    submitted = _submit(http, work)
    assert submitted.status_code == 200, submitted.content
    assert submitted.json()["status"] == WorkStatus.READY_FOR_REVIEW

    premature = http.post(
        f"/api/v1/work-items/{work.id}/approve/",
        data={},
        content_type="application/json",
        **_headers(principal=REVIEWER),
    )
    assert premature.status_code == 400
    assert premature.json()["code"] == "QA_REVIEW_BLOCKED"

    reviewed = http.post(
        f"/api/v1/work-items/{work.id}/save-reviewer-checklist/",
        data={"responses": [{"id": response_id, "value": "YES"}]},
        content_type="application/json",
        **_headers(principal=REVIEWER),
    )
    assert reviewed.status_code == 200, reviewed.content

    approved = http.post(
        f"/api/v1/work-items/{work.id}/approve/",
        data={"comment": "QA passed"},
        content_type="application/json",
        **_headers(principal=REVIEWER),
    )
    assert approved.status_code == 200, approved.content
    assert approved.json()["status"] == WorkStatus.COMPLETED

    qa_cycle = QAReviewCycle.objects.get(id=cycle["id"])
    assert qa_cycle.status == QAReviewCycleStatus.APPROVED
    assert qa_cycle.approved_at is not None


@pytest.mark.django_db
def test_open_issue_blocks_approval_until_owner_resolves_it():
    http = HttpClient()
    work = _setup_work()
    cycle = _prepare(http, work)
    response_id = cycle["responses"][0]["id"]
    _save_preparer(http, work, response_id)
    assert _submit(http, work).status_code == 200

    reviewed = http.post(
        f"/api/v1/work-items/{work.id}/save-reviewer-checklist/",
        data={"responses": [{"id": response_id, "value": "YES"}]},
        content_type="application/json",
        **_headers(principal=REVIEWER),
    )
    assert reviewed.status_code == 200, reviewed.content

    raised = http.post(
        f"/api/v1/work-items/{work.id}/raise-qa-issue/",
        data={
            "title": "Incorrect tax total",
            "description": "Recalculate the liability.",
            "severity": "HIGH",
        },
        content_type="application/json",
        **_headers(principal=REVIEWER),
    )
    assert raised.status_code == 201, raised.content
    issue_id = raised.json()["issue_id"]

    blocked = http.post(
        f"/api/v1/work-items/{work.id}/approve/",
        data={},
        content_type="application/json",
        **_headers(principal=REVIEWER),
    )
    assert blocked.status_code == 400
    assert blocked.json()["code"] == "QA_REVIEW_BLOCKED"

    returned = http.post(
        f"/api/v1/work-items/{work.id}/return_for_rework/",
        data={"comment": "Correct the tax total"},
        content_type="application/json",
        **_headers(principal=REVIEWER),
    )
    assert returned.status_code == 200, returned.content

    resolved = http.post(
        f"/api/v1/work-items/{work.id}/resolve-qa-issue/",
        data={"issue_id": issue_id, "comment": "Tax total corrected."},
        content_type="application/json",
        **_headers(),
    )
    assert resolved.status_code == 200, resolved.content
    assert resolved.json()["status"] == QAIssueStatus.RESOLVED

    issue = QAReviewIssue.objects.get(id=issue_id)
    assert issue.status == QAIssueStatus.RESOLVED
    cycle_row = QAReviewCycle.objects.get(id=cycle["id"])
    assert cycle_row.status == QAReviewCycleStatus.CHANGES_REQUESTED


@pytest.mark.django_db
def test_self_review_is_blocked_by_active_checklist_policy():
    http = HttpClient()
    work = _setup_work(reviewer_principal=OWNER)
    cycle = _prepare(http, work)
    response_id = cycle["responses"][0]["id"]
    _save_preparer(http, work, response_id)

    submitted = _submit(http, work)
    assert submitted.status_code == 400
    assert submitted.json()["code"] == "QA_CHECKLIST_BLOCKED"
    blocker_codes = {
        blocker["code"]
        for blocker in submitted.json()["qa_readiness"]["submission_blockers"]
    }
    assert "SELF_REVIEW_BLOCKED" in blocker_codes


@pytest.mark.django_db
def test_work_without_active_checklist_preserves_legacy_approval_contract():
    http = HttpClient()
    reviewer = Employee.objects.create(
        tenant_id=TENANT,
        created_by=OWNER,
        updated_by=OWNER,
        name="Legacy Reviewer",
        email="legacy-reviewer@example.com",
        principal_id=REVIEWER,
        is_active=True,
    )
    work = WorkItem.objects.create(
        tenant_id=TENANT,
        created_by=OWNER,
        updated_by=OWNER,
        title="Legacy Work",
        client_id=uuid.uuid4(),
        owner_user_id=OWNER,
        reviewer_user_id=reviewer.id,
        status=WorkStatus.IN_PROGRESS,
    )

    submitted = _submit(http, work)
    assert submitted.status_code == 200, submitted.content
    approved = http.post(
        f"/api/v1/work-items/{work.id}/approve/",
        data={},
        content_type="application/json",
        **_headers(principal=REVIEWER),
    )
    assert approved.status_code == 200, approved.content
    assert approved.json()["status"] == WorkStatus.COMPLETED
