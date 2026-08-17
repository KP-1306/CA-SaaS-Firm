from __future__ import annotations

import uuid

import pytest
from django.test import Client as HttpClient
from django.utils import timezone


TENANT = "11111111-1111-1111-1111-111111111111"
OWNER = "44444444-4444-4444-4444-444444444444"
REVIEWER = "55555555-5555-5555-5555-555555555555"
CREATOR = "22222222-2222-2222-2222-222222222222"


def _headers(principal):
    return {
        "HTTP_X_TENANT_ID": TENANT,
        "HTTP_X_PRINCIPAL_ID": principal,
    }


def _employee(principal, name):
    from contexts.identity.models import Employee

    return Employee.objects.create(
        tenant_id=TENANT,
        created_by=CREATOR,
        updated_by=CREATOR,
        name=name,
        email=f"{name.lower()}-{principal}@example.com",
        role="STAFF",
        principal_id=principal,
        is_active=True,
    )


def _service():
    from contexts.configuration.models import Service

    return Service.objects.create(
        tenant_id=TENANT,
        created_by=CREATOR,
        updated_by=CREATOR,
        domain_id=uuid.uuid4(),
        name="MSME (Udyam) Registration",
        code="UDYAM_REGISTRATION",
        description="Focused Udyam workflow regression service.",
    )


def _step(service, code, order):
    from contexts.configuration.models import ServiceProcessStep

    return ServiceProcessStep.objects.create(
        tenant_id=TENANT,
        created_by=CREATOR,
        updated_by=CREATOR,
        service_id=service.id,
        code=code,
        name=code.replace("_", " ").title(),
        description="Focused Udyam workflow regression step.",
        display_order=order,
        is_active=True,
    )


def _work(service):
    from contexts.work.models import WorkItem

    owner = _employee(OWNER, "UdyamOwner")
    reviewer = _employee(REVIEWER, "UdyamReviewer")

    return WorkItem.objects.create(
        tenant_id=TENANT,
        created_by=CREATOR,
        updated_by=CREATOR,
        title="Udyam Review Progression",
        client_id=uuid.uuid4(),
        service_id=service.id,
        owner_user_id=owner.id,
        reviewer_user_id=reviewer.id,
        priority="NORMAL",
        status="IN_PROGRESS",
    )


def _process(service):
    return {
        "verification": _step(
            service,
            "VERIFICATION_PREPARATION",
            20,
        ),
        "review": _step(
            service,
            "INTERNAL_REVIEW",
            30,
        ),
        "submit": _step(
            service,
            "SUBMIT_APPLICATION",
            35,
        ),
        "submission": _step(
            service,
            "APPLICATION_SUBMISSION",
            40,
        ),
        "query": _step(
            service,
            "QUERY_RESOLUTION",
            50,
        ),
        "completion": _step(
            service,
            "COMPLETION",
            60,
        ),
    }


def _patch_dependencies(monkeypatch):
    import contexts.work.views as views

    monkeypatch.setattr(
        views,
        "calculate_document_readiness",
        lambda item: {
            "ready_for_review": True,
            "missing": 0,
            "mandatory_missing": 0,
        },
    )

    monkeypatch.setattr(
        views,
        "qa_prepare_cycle",
        lambda *args, **kwargs: None,
    )

    monkeypatch.setattr(
        views,
        "qa_readiness",
        lambda item: {
            "enabled": False,
            "ready_for_submission": True,
            "ready_for_approval": True,
        },
    )

    monkeypatch.setattr(
        views,
        "qa_mark_submitted",
        lambda *args, **kwargs: object(),
    )

    monkeypatch.setattr(
        views,
        "qa_mark_approved",
        lambda *args, **kwargs: object(),
    )

    monkeypatch.setattr(
        views,
        "qa_mark_changes_requested",
        lambda *args, **kwargs: object(),
    )

    monkeypatch.setattr(
        views,
        "qa_cycle_summary",
        lambda cycle: {},
    )

    monkeypatch.setattr(
        views,
        "notify_work_transition",
        lambda *args, **kwargs: None,
    )


@pytest.mark.django_db
def test_udyam_submit_then_approve_advances_to_application_submission(
    monkeypatch,
):
    from contexts.work.models import WorkProcessState

    _patch_dependencies(monkeypatch)

    service = _service()
    steps = _process(service)
    work = _work(service)
    http = HttpClient()

    submitted = http.post(
        f"/api/v1/work-items/{work.id}/submit_for_review/",
        data={},
        content_type="application/json",
        **_headers(OWNER),
    )

    assert submitted.status_code == 200, submitted.content

    work.refresh_from_db()

    assert work.status == "READY_FOR_REVIEW"
    assert work.completed_at is None

    state = WorkProcessState.objects.get(
        tenant_id=TENANT,
        work_item_id=work.id,
    )

    assert state.current_step_id == steps["review"].id

    approved = http.post(
        f"/api/v1/work-items/{work.id}/approve/",
        data={},
        content_type="application/json",
        **_headers(REVIEWER),
    )

    assert approved.status_code == 200, approved.content

    work.refresh_from_db()
    state.refresh_from_db()

    assert work.status == "IN_PROGRESS"
    assert work.completed_at is None
    assert state.current_step_id == steps["submit"].id

    payload = approved.json()

    assert payload["status"] == "IN_PROGRESS"
    assert payload["current_controller"] == "OWNER"
    # Approval response is serialized for the reviewer principal.
    # Control has returned to OWNER, therefore reviewer-side locking
    # may remain true even though the Work Item is operational.
    owner_view = http.get(
        f"/api/v1/work-items/{work.id}/",
        **_headers(OWNER),
    )

    assert owner_view.status_code == 200, owner_view.content

    owner_payload = owner_view.json()

    assert owner_payload["status"] == "IN_PROGRESS"
    assert owner_payload["current_controller"] == "OWNER"
    assert owner_payload["is_locked"] is False
    assert owner_payload["can_edit"] is True


@pytest.mark.django_db
def test_udyam_rework_returns_process_to_verification(
    monkeypatch,
):
    from contexts.work.models import WorkProcessState

    _patch_dependencies(monkeypatch)

    service = _service()
    steps = _process(service)
    work = _work(service)
    http = HttpClient()

    submitted = http.post(
        f"/api/v1/work-items/{work.id}/submit_for_review/",
        data={},
        content_type="application/json",
        **_headers(OWNER),
    )

    assert submitted.status_code == 200, submitted.content

    returned = http.post(
        f"/api/v1/work-items/{work.id}/return_for_rework/",
        data={"comment": "Correct the application details."},
        content_type="application/json",
        **_headers(REVIEWER),
    )

    assert returned.status_code == 200, returned.content

    work.refresh_from_db()

    state = WorkProcessState.objects.get(
        tenant_id=TENANT,
        work_item_id=work.id,
    )

    assert work.status == "REWORK_REQUIRED"
    assert work.completed_at is None
    assert state.current_step_id == steps["verification"].id


@pytest.mark.django_db
def test_udyam_stage_four_cannot_reenter_internal_review(
    monkeypatch,
):
    from contexts.work.models import WorkProcessState

    _patch_dependencies(monkeypatch)

    service = _service()
    steps = _process(service)
    work = _work(service)

    WorkProcessState.objects.create(
        tenant_id=TENANT,
        created_by=CREATOR,
        updated_by=CREATOR,
        work_item_id=work.id,
        current_step_id=steps["submission"].id,
        entered_at=timezone.now(),
        entered_by=REVIEWER,
        note="Internal review already completed.",
    )

    response = HttpClient().post(
        f"/api/v1/work-items/{work.id}/submit_for_review/",
        data={},
        content_type="application/json",
        **_headers(OWNER),
    )

    assert response.status_code == 409
    assert (
        response.json()["code"]
        == "UDYAM_INTERNAL_REVIEW_ALREADY_COMPLETED"
    )




@pytest.mark.django_db
def test_udyam_stage4_requires_submission_details_and_advances_to_completion(
    monkeypatch,
):
    from contexts.work.models import WorkProcessState

    _patch_dependencies(monkeypatch)

    service = _service()
    steps = _process(service)
    work = _work(service)

    WorkProcessState.objects.create(
        tenant_id=TENANT,
        created_by=CREATOR,
        updated_by=CREATOR,
        work_item_id=work.id,
        current_step_id=steps["submit"].id,
        entered_at=timezone.now(),
        entered_by=REVIEWER,
        note="Internal review approved.",
    )

    http = HttpClient()

    missing = http.post(
        f"/api/v1/work-items/{work.id}/udyam-submit-application/",
        data={},
        content_type="application/json",
        **_headers(OWNER),
    )

    assert missing.status_code == 400

    response = http.post(
        f"/api/v1/work-items/{work.id}/udyam-submit-application/",
        data={
            "application_reference": "UDYAM-REF-001",
            "submission_date": "2026-08-12",
            "submission_time": "14:30",
        },
        content_type="application/json",
        **_headers(OWNER),
    )

    assert response.status_code == 200, response.content

    work.refresh_from_db()

    assert (
        work.operational_data["udyam_application_reference"]
        == "UDYAM-REF-001"
    )
    assert (
        work.operational_data["udyam_submission_date"]
        == "2026-08-12"
    )
    assert work.status == "IN_PROGRESS"

    state = WorkProcessState.objects.get(
        tenant_id=TENANT,
        work_item_id=work.id,
    )

    assert state.current_step_id == steps["submission"].id


@pytest.mark.django_db
def test_udyam_stage6_query_can_resolve_back_to_stage6(
    monkeypatch,
):
    from contexts.work.models import WorkProcessState

    _patch_dependencies(monkeypatch)

    service = _service()
    steps = _process(service)
    work = _work(service)

    state = WorkProcessState.objects.create(
        tenant_id=TENANT,
        created_by=CREATOR,
        updated_by=CREATOR,
        work_item_id=work.id,
        current_step_id=steps["submission"].id,
        entered_at=timezone.now(),
        entered_by=OWNER,
        note="Application submitted.",
    )

    http = HttpClient()

    query = http.post(
        f"/api/v1/work-items/{work.id}/udyam-report-query/",
        data={
            "query_type": "OTP_REQUIRED",
            "remarks": "OTP requested by government portal.",
        },
        content_type="application/json",
        **_headers(OWNER),
    )

    assert query.status_code == 200, query.content

    state.refresh_from_db()
    assert state.current_step_id == steps["query"].id

    resolved = http.post(
        f"/api/v1/work-items/{work.id}/udyam-resolve-query/",
        data={
            "remarks": "OTP completed successfully.",
        },
        content_type="application/json",
        **_headers(OWNER),
    )

    assert resolved.status_code == 200, resolved.content

    state.refresh_from_db()
    assert state.current_step_id == steps["submission"].id

    work.refresh_from_db()
    assert work.status == "IN_PROGRESS"

