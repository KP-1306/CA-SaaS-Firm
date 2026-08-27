from __future__ import annotations

import uuid

import pytest
from django.test import Client as HttpClient


TENANT = "11111111-1111-1111-1111-111111111111"
OWNER = "44444444-4444-4444-4444-444444444444"
REVIEWER = "55555555-5555-5555-5555-555555555555"
CREATOR = "22222222-2222-2222-2222-222222222222"

MUDRA_STEPS = [
    ("APPLICATION", 10),
    ("CREDIT_ELIGIBILITY", 20),
    ("FILE_PREPARATION", 30),
    ("BANK_SUBMITTED", 40),
    ("BANK_VERIFICATION", 50),
    ("BANK_PENDING", 60),
    ("RO_REVIEW", 70),
    ("SANCTIONED", 80),
    ("DISBURSEMENT", 90),
    ("CLOSED", 100),
]


def _headers(principal):
    return {"HTTP_X_TENANT_ID": TENANT, "HTTP_X_PRINCIPAL_ID": principal}


def _employee(principal, name):
    from contexts.identity.models import Employee

    return Employee.objects.create(
        tenant_id=TENANT, created_by=CREATOR, updated_by=CREATOR,
        name=name, email=f"{name.lower()}-{principal}@example.com",
        role="STAFF", principal_id=principal, is_active=True,
    )


def _service(code="MUDRA_LOAN", name="Mudra Loan"):
    from contexts.configuration.models import Service

    return Service.objects.create(
        tenant_id=TENANT, created_by=CREATOR, updated_by=CREATOR,
        domain_id=uuid.uuid4(), name=name, code=code,
        description="Mudra end-to-end runtime test service.",
    )


def _step(service, code, order):
    from contexts.configuration.models import ServiceProcessStep

    return ServiceProcessStep.objects.create(
        tenant_id=TENANT, created_by=CREATOR, updated_by=CREATOR,
        service_id=service.id, code=code,
        name=code.replace("_", " ").title(),
        description="Mudra process step.", display_order=order, is_active=True,
    )


def _steps(service):
    return {code: _step(service, code, order) for code, order in MUDRA_STEPS}


def _work(service, owner):
    from contexts.work.models import WorkItem

    return WorkItem.objects.create(
        tenant_id=TENANT, created_by=CREATOR, updated_by=CREATOR,
        title="Mudra Case", client_id=uuid.uuid4(), service_id=service.id,
        owner_user_id=owner.id, reviewer_user_id=uuid.uuid4(),
        priority="NORMAL", status="IN_PROGRESS",
    )


def _seed_state(work, step):
    from contexts.work.models import WorkProcessState
    from django.utils import timezone

    return WorkProcessState.objects.create(
        tenant_id=TENANT, created_by=CREATOR, updated_by=CREATOR,
        work_item_id=work.id, current_step_id=step.id,
        entered_at=timezone.now(),
        entered_by=OWNER, note="seed",
    )


def _state(work):
    from contexts.work.models import WorkProcessState

    return WorkProcessState.objects.get(tenant_id=TENANT, work_item_id=work.id)


def _post(client, work, verb, data, principal=OWNER):
    return client.post(
        f"/api/v1/work-items/{work.id}/{verb}/",
        data=data, content_type="application/json", **_headers(principal),
    )


def _patch_dependencies(monkeypatch):
    """
    Neutralize document-readiness and QA gating so the mandatory real-lifecycle
    tests exercise the Mudra/generic-Work review bridge itself, not unrelated
    document/QA configuration. Mirrors the exact pattern already used by
    test_udyam_review_progression.py for the same real submit/approve/return
    actions - not a new test convention.
    """
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
    monkeypatch.setattr(views, "qa_prepare_cycle", lambda *a, **k: None)
    monkeypatch.setattr(
        views,
        "qa_readiness",
        lambda item: {
            "enabled": False,
            "ready_for_submission": True,
            "ready_for_approval": True,
        },
    )
    monkeypatch.setattr(views, "qa_mark_submitted", lambda *a, **k: object())
    monkeypatch.setattr(views, "qa_mark_approved", lambda *a, **k: object())
    monkeypatch.setattr(views, "qa_mark_changes_requested", lambda *a, **k: object())
    monkeypatch.setattr(views, "qa_cycle_summary", lambda cycle: {})


def _real_mudra_work(client, service, owner, reviewer):
    """Create an actual Mudra Work item through the real create API (not ORM
    seeding), matching the acceptance contract's "create through the real
    API" requirement for the mandatory lifecycle tests."""
    res = client.post(
        "/api/v1/work-items/",
        data={
            "title": "Real Mudra Case",
            "client_id": str(uuid.uuid4()),
            "service_id": str(service.id),
            "owner_user_id": str(owner.id),
            "reviewer_user_id": str(reviewer.id),
            "priority": "NORMAL",
            "status": "IN_PROGRESS",
        },
        content_type="application/json",
        **_headers(OWNER),
    )
    assert res.status_code in (200, 201), res.content
    from contexts.work.models import WorkItem

    return WorkItem.objects.get(tenant_id=TENANT, id=res.json()["id"])


def _real_review_approved_mudra_work(client, service, owner, reviewer):
    """
    Build a real Mudra Work through the real API, submit it for review, and
    have the real reviewer approve it - i.e. the real browser-equivalent path
    up to CREDIT_ELIGIBILITY. Used as the common starting point for the CIBIL/
    eligibility/full-lifecycle tests so each does not have to re-derive the
    review bridge from scratch.
    """
    work = _real_mudra_work(client, service, owner, reviewer)

    submitted = _post(client, work, "submit_for_review", {})
    assert submitted.status_code == 200, submitted.content

    approved = _post(client, work, "approve", {"comment": "Looks complete."}, principal=REVIEWER)
    assert approved.status_code == 200, approved.content

    from contexts.work.models import WorkItem

    return WorkItem.objects.get(tenant_id=TENANT, id=work.id)


# ---------------------------------------------------------------- B. init
@pytest.mark.django_db
def test_initialization_sets_application_stage():
    from contexts.work.models import WorkProcessState

    service = _service()
    steps = _steps(service)
    owner = _employee(OWNER, "MudraOwner")
    client = HttpClient()
    res = client.post(
        "/api/v1/work-items/",
        data={
            "title": "New Mudra",
            "client_id": str(uuid.uuid4()),
            "service_id": str(service.id),
            "owner_user_id": str(owner.id),
            "priority": "NORMAL",
            "status": "IN_PROGRESS",
        },
        content_type="application/json",
        **_headers(OWNER),
    )
    assert res.status_code in (200, 201), res.content
    work_id = res.json()["id"]
    state = WorkProcessState.objects.get(tenant_id=TENANT, work_item_id=work_id)
    assert state.current_step_id == steps["APPLICATION"].id


@pytest.mark.django_db
def test_non_mudra_work_does_not_initialize_mudra_state():
    from contexts.work.models import WorkProcessState

    service = _service(code="HOME_LOAN", name="Home Loan")
    _steps(service)
    owner = _employee(OWNER, "HomeOwner")
    client = HttpClient()
    res = client.post(
        "/api/v1/work-items/",
        data={
            "title": "Home Loan",
            "client_id": str(uuid.uuid4()),
            "service_id": str(service.id),
            "owner_user_id": str(owner.id),
            "priority": "NORMAL",
            "status": "IN_PROGRESS",
        },
        content_type="application/json",
        **_headers(OWNER),
    )
    assert res.status_code in (200, 201)
    work_id = res.json()["id"]
    assert not WorkProcessState.objects.filter(
        tenant_id=TENANT, work_item_id=work_id
    ).exists()


# ---------------------------------------------------------------- C. application (in-place only)
#
# OLD CONTRACT: mudra-complete-application validated and recorded the
# Application/KYC fields AND advanced the Mudra process position from
# APPLICATION to CREDIT_ELIGIBILITY.
#
# NEW APPROVED CONTRACT (correction package root-cause #2 - the review
# bypass): mudra-complete-application still validates and records the same
# fields in place, but must NEVER advance the process position.
# APPLICATION -> CREDIT_ELIGIBILITY is owned exclusively by successful
# internal reviewer approval (WorkItemViewSet.approve's Mudra branch).
#
# WHY THIS TEST MUST CHANGE: its final assertion asserted the very owner-
# initiated position advancement the correction requires removed as a review
# bypass. Keeping that assertion would enforce a regression, not protect a
# contract, so it is replaced with an assertion that the position is
# unchanged. The field-validation/recording behavior (the other half of the
# original test) is unchanged and is preserved as-is below.
@pytest.mark.django_db
def test_application_requires_core_fields_and_does_not_advance():
    service = _service()
    steps = _steps(service)
    owner = _employee(OWNER, "MudraOwner")
    work = _work(service, owner)
    _seed_state(work, steps["APPLICATION"])
    client = HttpClient()

    missing = _post(client, work, "mudra-complete-application", {"loan_purpose": "x"})
    assert missing.status_code == 400

    ok = _post(client, work, "mudra-complete-application", {
        "requested_loan_amount": "50000", "loan_purpose": "Working capital",
    })
    assert ok.status_code == 200, ok.content
    # Fields are recorded...
    assert ok.json()["operational_data"]["requested_loan_amount"] == "50000"
    # ...but the process position does NOT advance. Only successful internal
    # review approval may move APPLICATION -> CREDIT_ELIGIBILITY.
    assert _state(work).current_step_id == steps["APPLICATION"].id


# ---------------------------------------------------------------- C2. no owner-edit while under review
@pytest.mark.django_db
def test_application_edit_blocked_while_ready_for_review():
    from contexts.work.models import WorkItem

    service = _service()
    steps = _steps(service)
    owner = _employee(OWNER, "MudraOwner")
    work = _work(service, owner)
    _seed_state(work, steps["APPLICATION"])
    WorkItem.objects.filter(tenant_id=TENANT, id=work.id).update(
        status="READY_FOR_REVIEW",
    )
    client = HttpClient()

    blocked = _post(client, work, "mudra-complete-application", {
        "requested_loan_amount": "50000", "loan_purpose": "Working capital",
    })
    assert blocked.status_code == 409
    assert blocked.json().get("code") == "MUDRA_NOT_OWNER_EDITABLE"
    # Position still unchanged.
    assert _state(work).current_step_id == steps["APPLICATION"].id


# ---------------------------------------------------------------- D. eligibility
@pytest.mark.django_db
def test_eligible_path_advances_to_file_preparation():
    service = _service()
    steps = _steps(service)
    owner = _employee(OWNER, "MudraOwner")
    work = _work(service, owner)
    _seed_state(work, steps["CREDIT_ELIGIBILITY"])
    client = HttpClient()

    _post(client, work, "mudra-record-cibil", {"cibil_score": "720"})
    res = _post(client, work, "mudra-decide-eligibility", {
        "eligibility_result": "ELIGIBLE", "eligibility_date": "2026-08-19",
    })
    assert res.status_code == 200, res.content
    assert _state(work).current_step_id == steps["FILE_PREPARATION"].id


@pytest.mark.django_db
def test_not_eligible_requires_reason_and_is_terminal_after_reload():
    from contexts.work.models import WorkItem

    service = _service()
    steps = _steps(service)
    owner = _employee(OWNER, "MudraOwner")
    work = _work(service, owner)
    _seed_state(work, steps["CREDIT_ELIGIBILITY"])
    client = HttpClient()

    no_reason = _post(client, work, "mudra-decide-eligibility", {
        "eligibility_result": "NOT_ELIGIBLE",
    })
    assert no_reason.status_code == 400

    res = _post(client, work, "mudra-decide-eligibility", {
        "eligibility_result": "NOT_ELIGIBLE", "rejection_reason": "Low CIBIL",
    })
    assert res.status_code == 200, res.content

    reloaded = WorkItem.objects.get(tenant_id=TENANT, id=work.id)
    assert (reloaded.operational_data or {}).get("mudra_outcome") == "REJECTED"
    assert (reloaded.operational_data or {}).get("rejection_reason") == "Low CIBIL"

    # Terminal: further advancement is blocked.
    blocked = _post(client, work, "mudra-complete-file-preparation", {
        "project_report_prepared": "YES",
    })
    assert blocked.status_code == 400
    assert blocked.json().get("code") == "MUDRA_CASE_REJECTED"


# ---------------------------------------------------------------- G. bank verify
@pytest.mark.django_db
def test_bank_verification_clear_goes_to_ro_review():
    service = _service()
    steps = _steps(service)
    owner = _employee(OWNER, "MudraOwner")
    work = _work(service, owner)
    _seed_state(work, steps["BANK_VERIFICATION"])
    client = HttpClient()

    res = _post(client, work, "mudra-record-bank-verification", {
        "bank_verification_status": "CLEAR", "bank_verification_date": "2026-08-19",
    })
    assert res.status_code == 200, res.content
    assert _state(work).current_step_id == steps["RO_REVIEW"].id


@pytest.mark.django_db
def test_bank_verification_pending_goes_to_bank_pending():
    service = _service()
    steps = _steps(service)
    owner = _employee(OWNER, "MudraOwner")
    work = _work(service, owner)
    _seed_state(work, steps["BANK_VERIFICATION"])
    client = HttpClient()

    res = _post(client, work, "mudra-record-bank-verification", {
        "bank_verification_status": "PENDING",
    })
    assert res.status_code == 200, res.content
    assert _state(work).current_step_id == steps["BANK_PENDING"].id


# ---------------------------------------------------------------- H. pending loop
@pytest.mark.django_db
def test_bank_pending_loop_returns_to_verification_not_ro():
    from contexts.work.models import WorkItem

    service = _service()
    steps = _steps(service)
    owner = _employee(OWNER, "MudraOwner")
    work = _work(service, owner)
    _seed_state(work, steps["BANK_PENDING"])
    client = HttpClient()

    raise_res = _post(client, work, "mudra-raise-pending-task", {
        "pending_reason": "Need updated bank statement",
    })
    assert raise_res.status_code == 200, raise_res.content

    reassign = _post(client, work, "mudra-reassign-pending-task", {
        "pending_assignee_user_id": str(uuid.uuid4()),
    })
    assert reassign.status_code == 200, reassign.content

    # Re-QC cannot run before evidence received.
    early_reqc = _post(client, work, "mudra-complete-reqc", {})
    assert early_reqc.status_code == 409

    evidence = _post(client, work, "mudra-record-pending-evidence", {
        "pending_evidence": "Statement received",
    })
    assert evidence.status_code == 200, evidence.content

    reqc = _post(client, work, "mudra-complete-reqc", {})
    assert reqc.status_code == 200, reqc.content
    # Returns to verification, NOT directly to RO review.
    assert _state(work).current_step_id == steps["BANK_VERIFICATION"].id

    reloaded = WorkItem.objects.get(tenant_id=TENANT, id=work.id)
    task = (reloaded.operational_data or {}).get("mudra_pending_task") or {}
    assert task.get("status") == "RESOLVED"
    assert task.get("reqc_status") == "COMPLETE"


# ---------------------------------------------------------------- J. sanction
@pytest.mark.django_db
def test_sanction_conditions_block_until_recorded_and_complete():
    service = _service()
    steps = _steps(service)
    owner = _employee(OWNER, "MudraOwner")
    work = _work(service, owner)
    _seed_state(work, steps["SANCTIONED"])
    client = HttpClient()

    # Conditions before sanction recorded -> blocked.
    blocked = _post(client, work, "mudra-complete-sanction-conditions", {
        "sanction_conditions_status": "COMPLETE",
    })
    assert blocked.status_code == 409

    _post(client, work, "mudra-record-sanction", {"sanctioned_amount": "50000"})

    incomplete = _post(client, work, "mudra-complete-sanction-conditions", {
        "sanction_conditions_status": "PENDING",
    })
    assert incomplete.status_code == 400

    ok = _post(client, work, "mudra-complete-sanction-conditions", {
        "sanction_conditions_status": "COMPLETE",
    })
    assert ok.status_code == 200, ok.content
    assert _state(work).current_step_id == steps["DISBURSEMENT"].id


# ---------------------------------------------------------------- K/L. disburse+close
@pytest.mark.django_db
def test_disbursement_ready_distinct_from_disbursement_and_closes():
    from contexts.work.models import WorkItem

    service = _service()
    steps = _steps(service)
    owner = _employee(OWNER, "MudraOwner")
    work = _work(service, owner)
    _seed_state(work, steps["DISBURSEMENT"])
    client = HttpClient()

    # Disburse before ready -> blocked.
    early = _post(client, work, "mudra-record-disbursement", {
        "disbursed_amount": "50000", "disbursement_date": "2026-08-19",
    })
    assert early.status_code == 409

    ready = _post(client, work, "mudra-mark-disbursement-ready", {
        "disbursement_ready_date": "2026-08-19",
    })
    assert ready.status_code == 200, ready.content
    # Still in DISBURSEMENT after ready.
    assert _state(work).current_step_id == steps["DISBURSEMENT"].id

    disburse = _post(client, work, "mudra-record-disbursement", {
        "disbursed_amount": "50000", "disbursement_date": "2026-08-19",
    })
    assert disburse.status_code == 200, disburse.content
    assert _state(work).current_step_id == steps["CLOSED"].id

    reloaded = WorkItem.objects.get(tenant_id=TENANT, id=work.id)
    assert (reloaded.operational_data or {}).get("mudra_outcome") == "CLOSED"
    assert reloaded.completed_at is not None
    # WorkItem.status must reach COMPLETED via the shared, frozen _transition
    # mechanism (the same one the Udyam completion action uses) - not just the
    # Mudra-specific operational_data outcome flag.
    assert reloaded.status == "COMPLETED"
    assert _state(work).current_step_id == steps["CLOSED"].id

    # Reload/re-fetch (a fresh query, independent of the objects used above)
    # must preserve all four facts together.
    refetched = WorkItem.objects.get(tenant_id=TENANT, id=work.id)
    refetched_state = _state(work)
    assert refetched_state.current_step_id == steps["CLOSED"].id
    assert (refetched.operational_data or {}).get("mudra_outcome") == "CLOSED"
    assert refetched.status == "COMPLETED"
    assert refetched.completed_at is not None

    # Terminal after reload: cannot re-run a disbursement.
    again = _post(client, work, "mudra-record-disbursement", {
        "disbursed_amount": "1", "disbursement_date": "2026-08-20",
    })
    assert again.status_code in (400, 409)


# ---------------------------------------------------------------- wrong-position guard
@pytest.mark.django_db
def test_action_rejected_from_wrong_position():
    service = _service()
    steps = _steps(service)
    owner = _employee(OWNER, "MudraOwner")
    work = _work(service, owner)
    _seed_state(work, steps["APPLICATION"])
    client = HttpClient()

    # Bank verification from APPLICATION -> position required error.
    res = _post(client, work, "mudra-record-bank-verification", {
        "bank_verification_status": "CLEAR",
    })
    assert res.status_code == 400
    assert res.json().get("code") == "MUDRA_PROCESS_POSITION_REQUIRED"


# ---------------------------------------------------------------- O. isolation
@pytest.mark.django_db
def test_mudra_action_rejected_for_non_mudra_service():
    service = _service(code="HOME_LOAN", name="Home Loan")
    steps = _steps(service)
    owner = _employee(OWNER, "HomeOwner")
    work = _work(service, owner)
    _seed_state(work, steps["APPLICATION"])
    client = HttpClient()

    res = _post(client, work, "mudra-complete-application", {
        "requested_loan_amount": "1", "loan_purpose": "x",
    })
    assert res.status_code == 400
    assert res.json().get("code") == "MUDRA_SERVICE_REQUIRED"


# ---------------------------------------------------------------- state endpoint
@pytest.mark.django_db
def test_mudra_state_endpoint_reports_authoritative_stage():
    service = _service()
    steps = _steps(service)
    owner = _employee(OWNER, "MudraOwner")
    work = _work(service, owner)
    _seed_state(work, steps["RO_REVIEW"])
    client = HttpClient()

    res = client.get(
        f"/api/v1/work-items/{work.id}/mudra-state/", **_headers(OWNER)
    )
    assert res.status_code == 200, res.content
    assert res.json()["current_step"]["code"] == "RO_REVIEW"


# ====================================================================
# MANDATORY REAL-LIFECYCLE INTEGRATION TESTS (correction package
# 00_GOVERNANCE/03_ACCEPTANCE_CONTRACT.md, sections A-I).
#
# These begin from an ACTUAL Mudra Work created through the real API and
# drive it through the real submit_for_review / approve / stage-action
# endpoints - not seeded WorkProcessState positions. The existing focused
# stage tests above remain valid (they prove each handler in isolation);
# these prove the real, integrated browser-equivalent journey the original
# implementation's test suite did not cover, which is exactly the gap the
# correction package identifies as the "verified test gap".
# ====================================================================

# ---------------------------------------------------------------- A/D/E. real review bridge + persistence
@pytest.mark.django_db
def test_A_real_review_bridge_reaches_credit_eligibility(monkeypatch):
    from contexts.work.models import WorkItem, WorkProcessState

    _patch_dependencies(monkeypatch)
    service = _service()
    steps = _steps(service)
    owner = _employee(OWNER, "MudraOwner")
    reviewer = _employee(REVIEWER, "MudraReviewer")
    client = HttpClient()

    work = _real_mudra_work(client, service, owner, reviewer)

    # Mudra begins at APPLICATION on real creation.
    state = WorkProcessState.objects.get(tenant_id=TENANT, work_item_id=work.id)
    assert state.current_step_id == steps["APPLICATION"].id

    # Satisfy review prerequisites (Application/KYC details) via the real
    # in-place recording action.
    fields_saved = _post(client, work, "mudra-complete-application", {
        "requested_loan_amount": "80000", "loan_purpose": "Working capital",
    })
    assert fields_saved.status_code == 200, fields_saved.content
    # Still at APPLICATION - recording fields does not advance the case.
    assert _state(work).current_step_id == steps["APPLICATION"].id

    submitted = _post(client, work, "submit_for_review", {})
    assert submitted.status_code == 200, submitted.content
    assert submitted.json()["status"] == "READY_FOR_REVIEW"
    # D: Application data is actually persisted before Submit for Review and
    # survives the submission transition itself - a fresh, independent
    # re-fetch right after submit_for_review, not the response body above.
    after_submit = WorkItem.objects.get(tenant_id=TENANT, id=work.id)
    assert (after_submit.operational_data or {}).get("requested_loan_amount") == "80000"
    assert (after_submit.operational_data or {}).get("loan_purpose") == "Working capital"

    approved = _post(
        client, work, "approve", {"comment": "Application reviewed."},
        principal=REVIEWER,
    )
    assert approved.status_code == 200, approved.content

    # Reload (fresh queries, independent of any object used above).
    reloaded = WorkItem.objects.get(tenant_id=TENANT, id=work.id)
    reloaded_state = WorkProcessState.objects.get(
        tenant_id=TENANT, work_item_id=work.id,
    )

    assert reloaded.status == "IN_PROGRESS"
    assert reloaded.completed_at is None
    assert reloaded_state.current_step_id == steps["CREDIT_ELIGIBILITY"].id
    # D (continued): the same data still survives reopen after reviewer
    # approval, not just immediately after being recorded.
    assert (reloaded.operational_data or {}).get("requested_loan_amount") == "80000"
    assert (reloaded.operational_data or {}).get("loan_purpose") == "Working capital"

    outcome = str((reloaded.operational_data or {}).get("mudra_outcome") or "")
    assert outcome != "CLOSED"
    assert outcome != "REJECTED"

    # Work is not terminal; owner can continue; CIBIL action is available -
    # i.e. the CIBIL action succeeds now that the case is at CREDIT_ELIGIBILITY.
    cibil = _post(client, work, "mudra-record-cibil", {"cibil_score": "710"})
    assert cibil.status_code == 200, cibil.content


# ---------------------------------------------------------------- B. return for rework
@pytest.mark.django_db
def test_B_return_for_rework_then_resubmit_then_approve(monkeypatch):
    from contexts.work.models import WorkItem, WorkProcessState

    _patch_dependencies(monkeypatch)
    service = _service()
    steps = _steps(service)
    owner = _employee(OWNER, "MudraOwner")
    reviewer = _employee(REVIEWER, "MudraReviewer")
    client = HttpClient()

    # A. Create real Mudra Work.
    work = _real_mudra_work(client, service, owner, reviewer)

    # B. Owner prepares the case.
    _post(client, work, "mudra-complete-application", {
        "requested_loan_amount": "80000", "loan_purpose": "Working capital",
    })

    # C. Owner Submit for Review.
    submitted = _post(client, work, "submit_for_review", {})
    assert submitted.status_code == 200, submitted.content

    # D. Reviewer Return for Rework.
    returned = _post(
        client, work, "return_for_rework",
        {"comment": "Please attach the missing KYC document."},
        principal=REVIEWER,
    )
    assert returned.status_code == 200, returned.content

    # E. Reload (independent, fresh queries) and assert.
    after_return = WorkItem.objects.get(tenant_id=TENANT, id=work.id)
    assert after_return.status == "REWORK_REQUIRED"
    assert after_return.completed_at is None
    # Mudra position is unaffected by rework - it never left APPLICATION
    # (the current source/test fixture's pre-review process position; no
    # invented stage name).
    assert _state(work).current_step_id == steps["APPLICATION"].id

    # F. Owner performs the EXISTING, certified Resume Work transition
    # through the real API - the same contract the generic frontend already
    # uses (workPrimaryAction(REWORK_REQUIRED) -> RESUME_WORK ->
    # executePendingWorkAction -> set_status {"status": "IN_PROGRESS"}).
    # This step was missing from the original test, which is the verified
    # root cause of the failure: it is a test journey defect, not a
    # production runtime defect (set_status already supports
    # REWORK_REQUIRED -> IN_PROGRESS per _ALLOWED_TRANSITIONS).
    resumed = _post(client, work, "set_status", {"status": "IN_PROGRESS"})
    assert resumed.status_code == 200, resumed.content

    # G. Reload independently and assert.
    after_resume = WorkItem.objects.get(tenant_id=TENANT, id=work.id)
    assert after_resume.status == "IN_PROGRESS"
    assert after_resume.completed_at is None
    assert after_resume.status not in ("COMPLETED", "CANCELLED")  # not terminal
    assert resumed.json().get("can_edit") is True
    # Mudra WorkProcessState has NOT incorrectly advanced merely because the
    # WorkItem was resumed.
    assert _state(work).current_step_id == steps["APPLICATION"].id

    # H. Owner corrects/persists data.
    corrected = _post(client, work, "mudra-complete-application", {
        "requested_loan_amount": "90000", "loan_purpose": "Working capital, revised",
    })
    assert corrected.status_code == 200, corrected.content

    # I. Owner calls the EXISTING submit_for_review (now valid: IN_PROGRESS).
    resubmitted = _post(client, work, "submit_for_review", {})

    # J. Assert the owner-side response and then independently prove
    # reviewer control with a reviewer-authenticated detail fetch.
    assert resubmitted.status_code == 200, resubmitted.content
    after_resubmit = WorkItem.objects.get(tenant_id=TENANT, id=work.id)
    assert after_resubmit.status == "READY_FOR_REVIEW"
    assert after_resubmit.completed_at is None

    # submit_for_review was called as OWNER, so the returned serializer is
    # correctly evaluated in the owner's security context. The owner must not
    # gain reviewer authority merely because the item is ready for review.
    assert resubmitted.json().get("can_review") is False
    assert resubmitted.json().get("can_edit") is False

    # Prove actual reviewer control using an independent reviewer-authenticated
    # fetch rather than asserting reviewer permissions on the owner's response.
    reviewer_view = client.get(
        f"/api/v1/work-items/{work.id}/",
        **_headers(REVIEWER),
    )
    assert reviewer_view.status_code == 200, reviewer_view.content
    assert reviewer_view.json().get("can_review") is True
    assert reviewer_view.json().get("can_edit") is False

    # Process position has not incorrectly jumped to CREDIT_ELIGIBILITY
    # merely from resubmission.
    assert _state(work).current_step_id == steps["APPLICATION"].id

    # K. Reviewer executes the existing Approve & Continue.
    approved = _post(
        client, work, "approve", {"comment": "Now complete."}, principal=REVIEWER,
    )
    assert approved.status_code == 200, approved.content

    # L. Reload independently.
    after_approve = WorkItem.objects.get(tenant_id=TENANT, id=work.id)
    after_approve_state = WorkProcessState.objects.get(
        tenant_id=TENANT, work_item_id=work.id,
    )

    # M. Assert the approved Mudra continuation contract.
    assert after_approve.status == "IN_PROGRESS"
    assert after_approve.completed_at is None
    assert after_approve_state.current_step_id == steps["CREDIT_ELIGIBILITY"].id
    assert after_approve.status != "COMPLETED"
    outcome = str((after_approve.operational_data or {}).get("mudra_outcome") or "")
    assert outcome not in ("REJECTED", "CLOSED")
    # Owner can continue to CIBIL / eligibility processing.
    cibil = _post(client, work, "mudra-record-cibil", {"cibil_score": "700"})
    assert cibil.status_code == 200, cibil.content


# ---------------------------------------------------------------- C. no bypass (real journey)
@pytest.mark.django_db
def test_C_real_journey_cannot_bypass_review(monkeypatch):
    _patch_dependencies(monkeypatch)
    service = _service()
    steps = _steps(service)
    owner = _employee(OWNER, "MudraOwner")
    reviewer = _employee(REVIEWER, "MudraReviewer")
    client = HttpClient()

    work = _real_mudra_work(client, service, owner, reviewer)

    # Even after recording valid Application/KYC fields, the owner cannot
    # advance to CREDIT_ELIGIBILITY merely by calling this action again.
    for _ in range(3):
        res = _post(client, work, "mudra-complete-application", {
            "requested_loan_amount": "80000", "loan_purpose": "Working capital",
        })
        assert res.status_code == 200, res.content
        assert _state(work).current_step_id == steps["APPLICATION"].id

    # Attempting the CREDIT_ELIGIBILITY-only CIBIL action from APPLICATION
    # is rejected by the process-position guard - there is no route to
    # CREDIT_ELIGIBILITY except successful review approval.
    premature = _post(client, work, "mudra-record-cibil", {"cibil_score": "700"})
    assert premature.status_code == 400
    assert premature.json().get("code") == "MUDRA_PROCESS_POSITION_REQUIRED"


# ---------------------------------------------------------------- D. CIBIL / eligible
@pytest.mark.django_db
def test_D_cibil_eligible_advances_to_file_preparation(monkeypatch):
    _patch_dependencies(monkeypatch)
    service = _service()
    steps = _steps(service)
    owner = _employee(OWNER, "MudraOwner")
    reviewer = _employee(REVIEWER, "MudraReviewer")
    client = HttpClient()

    _real_review_approved_mudra_work(client, service, owner, reviewer)
    work = WorkItem_by_owner(service, owner)

    _post(client, work, "mudra-record-cibil", {"cibil_score": "730"})
    decision = _post(client, work, "mudra-decide-eligibility", {
        "eligibility_result": "ELIGIBLE", "eligibility_date": "2026-08-20",
    })
    assert decision.status_code == 200, decision.content
    assert _state(work).current_step_id == steps["FILE_PREPARATION"].id


# ---------------------------------------------------------------- E. CIBIL / rejected
@pytest.mark.django_db
def test_E_cibil_not_eligible_rejects_and_stays_terminal_after_reload(monkeypatch):
    from contexts.work.models import WorkItem

    _patch_dependencies(monkeypatch)
    service = _service()
    steps = _steps(service)
    owner = _employee(OWNER, "MudraOwner")
    reviewer = _employee(REVIEWER, "MudraReviewer")
    client = HttpClient()

    _real_review_approved_mudra_work(client, service, owner, reviewer)
    work = WorkItem_by_owner(service, owner)

    _post(client, work, "mudra-record-cibil", {"cibil_score": "480"})

    no_reason = _post(client, work, "mudra-decide-eligibility", {
        "eligibility_result": "NOT_ELIGIBLE",
    })
    assert no_reason.status_code == 400

    rejected = _post(client, work, "mudra-decide-eligibility", {
        "eligibility_result": "NOT_ELIGIBLE", "rejection_reason": "Low CIBIL score",
    })
    assert rejected.status_code == 200, rejected.content

    reloaded = WorkItem.objects.get(tenant_id=TENANT, id=work.id)
    assert (reloaded.operational_data or {}).get("mudra_outcome") == "REJECTED"

    no_later_action = _post(client, work, "mudra-complete-file-preparation", {
        "project_report_prepared": "YES",
    })
    assert no_later_action.status_code == 400
    assert no_later_action.json().get("code") == "MUDRA_CASE_REJECTED"


def WorkItem_by_owner(service, owner):
    """Resolve the single Work item just created for this service/owner pair
    within the current test (helper used by tests that call
    _real_review_approved_mudra_work and then need the WorkItem handle)."""
    from contexts.work.models import WorkItem

    return WorkItem.objects.filter(
        tenant_id=TENANT, service_id=service.id, owner_user_id=owner.id,
    ).latest("created_at")


# ---------------------------------------------------------------- F-I. full real lifecycle
@pytest.mark.django_db
def test_FGHI_full_real_lifecycle_to_true_terminal_closure(monkeypatch):
    """
    Continues a real, reviewer-approved Mudra case through CIBIL -> ELIGIBLE
    -> Project Report -> Bank Submission -> Bank Verification PENDING ->
    the Bank Pending loop (assign/reassign/evidence/Re-QC, returning to Bank
    Verification, NOT jumping to RO Review) -> Bank Verification CLEAR ->
    RO Review -> Sanction -> Sanction Conditions -> Disbursement Ready ->
    Disbursement -> CLOSED. Proves durable state/evidence at each reload and
    the true terminal facts at the end.
    """
    from contexts.work.models import WorkItem, WorkProcessState

    _patch_dependencies(monkeypatch)
    service = _service()
    steps = _steps(service)
    owner = _employee(OWNER, "MudraOwner")
    reviewer = _employee(REVIEWER, "MudraReviewer")
    client = HttpClient()

    _real_review_approved_mudra_work(client, service, owner, reviewer)
    work = WorkItem_by_owner(service, owner)

    # -- D: CIBIL / ELIGIBLE -> FILE_PREPARATION
    _post(client, work, "mudra-record-cibil", {"cibil_score": "740"})
    elig = _post(client, work, "mudra-decide-eligibility", {
        "eligibility_result": "ELIGIBLE", "eligibility_date": "2026-08-20",
    })
    assert elig.status_code == 200, elig.content

    # -- F: Project Report / File Preparation -> BANK_SUBMITTED
    file_prep = _post(client, work, "mudra-complete-file-preparation", {
        "project_report_prepared": "YES", "project_report_date": "2026-08-20",
    })
    assert file_prep.status_code == 200, file_prep.content
    reloaded = WorkItem.objects.get(tenant_id=TENANT, id=work.id)
    assert (reloaded.operational_data or {}).get("project_report_prepared") == "YES"
    assert (
        WorkProcessState.objects.get(tenant_id=TENANT, work_item_id=work.id)
        .current_step_id == steps["BANK_SUBMITTED"].id
    )

    # -- G: Bank Submission -> BANK_VERIFICATION
    bank_submit = _post(client, work, "mudra-record-bank-submission", {
        "bank_name": "Test Bank", "bank_acknowledgement_date": "2026-08-20",
    })
    assert bank_submit.status_code == 200, bank_submit.content
    reloaded = WorkItem.objects.get(tenant_id=TENANT, id=work.id)
    assert (reloaded.operational_data or {}).get("bank_name") == "Test Bank"
    assert (
        WorkProcessState.objects.get(tenant_id=TENANT, work_item_id=work.id)
        .current_step_id == steps["BANK_VERIFICATION"].id
    )

    # -- H: Bank Query loop (PENDING -> assign/reassign -> evidence -> Re-QC
    #       -> back to BANK_VERIFICATION, NOT directly to RO_REVIEW/success)
    pending = _post(client, work, "mudra-record-bank-verification", {
        "bank_verification_status": "PENDING",
    })
    assert pending.status_code == 200, pending.content
    assert (
        WorkProcessState.objects.get(tenant_id=TENANT, work_item_id=work.id)
        .current_step_id == steps["BANK_PENDING"].id
    )

    raise_task = _post(client, work, "mudra-raise-pending-task", {
        "pending_reason": "Bank requested updated bank statement",
    })
    assert raise_task.status_code == 200, raise_task.content

    reassign = _post(client, work, "mudra-reassign-pending-task", {
        "pending_assignee_user_id": str(uuid.uuid4()),
    })
    assert reassign.status_code == 200, reassign.content

    evidence = _post(client, work, "mudra-record-pending-evidence", {
        "pending_evidence": "Updated statement uploaded",
    })
    assert evidence.status_code == 200, evidence.content

    reqc = _post(client, work, "mudra-complete-reqc", {})
    assert reqc.status_code == 200, reqc.content
    # Re-QC does NOT fabricate bank success - it returns to verification,
    # where the decision must be made again.
    assert (
        WorkProcessState.objects.get(tenant_id=TENANT, work_item_id=work.id)
        .current_step_id == steps["BANK_VERIFICATION"].id
    )

    # Reload throughout the loop preserved state (spot-check here after
    # completion): the resolved pending task remains in operational_data.
    reloaded = WorkItem.objects.get(tenant_id=TENANT, id=work.id)
    task = (reloaded.operational_data or {}).get("mudra_pending_task") or {}
    assert task.get("status") == "RESOLVED"

    # Now the actual bank response (CLEAR) moves the case forward.
    clear = _post(client, work, "mudra-record-bank-verification", {
        "bank_verification_status": "CLEAR",
    })
    assert clear.status_code == 200, clear.content
    assert (
        WorkProcessState.objects.get(tenant_id=TENANT, work_item_id=work.id)
        .current_step_id == steps["RO_REVIEW"].id
    )

    # -- RO Review -> SANCTIONED
    ro = _post(client, work, "mudra-complete-ro-review", {
        "ro_review_status": "REVIEWED",
    })
    assert ro.status_code == 200, ro.content

    # -- Sanction + Sanction Conditions -> DISBURSEMENT
    _post(client, work, "mudra-record-sanction", {"sanctioned_amount": "80000"})
    conditions = _post(client, work, "mudra-complete-sanction-conditions", {
        "sanction_conditions_status": "COMPLETE",
    })
    assert conditions.status_code == 200, conditions.content
    assert (
        WorkProcessState.objects.get(tenant_id=TENANT, work_item_id=work.id)
        .current_step_id == steps["DISBURSEMENT"].id
    )

    # -- I: Disbursement Ready -> Disbursement -> true terminal CLOSED
    _post(client, work, "mudra-mark-disbursement-ready", {
        "disbursement_ready_date": "2026-08-20",
    })
    disburse = _post(client, work, "mudra-record-disbursement", {
        "disbursed_amount": "80000", "disbursement_date": "2026-08-20",
    })
    assert disburse.status_code == 200, disburse.content

    # Reload/reopen: true terminal must be coherent.
    reloaded = WorkItem.objects.get(tenant_id=TENANT, id=work.id)
    reloaded_state = WorkProcessState.objects.get(
        tenant_id=TENANT, work_item_id=work.id,
    )
    assert reloaded.status == "COMPLETED"
    assert reloaded_state.current_step_id == steps["CLOSED"].id
    assert (reloaded.operational_data or {}).get("mudra_outcome") == "CLOSED"
    assert reloaded.completed_at is not None


# ====================================================================
# POST-REVIEW WORKSPACE RECONCILIATION (Work Health + effective_status).
#
# calculate_work_health() itself remains entirely generic and untouched -
# same precedent as Udyam. The service-aware next_action override lives in
# WorkItemViewSet.health(), which imports calculate_document_readiness
# separately from work_health.py's own import of the same underlying
# function - a distinct module binding, so _patch_dependencies (which only
# patches contexts.work.views.calculate_document_readiness) does not affect
# calls made through contexts.work.work_health.calculate_document_readiness.
# These tests patch that binding explicitly, with the full dict shape
# _document_health() actually reads, for deterministic results.
# ====================================================================

def _patch_work_health_document_readiness(monkeypatch, *, ready):
    import contexts.work.work_health as work_health

    monkeypatch.setattr(
        work_health,
        "calculate_document_readiness",
        lambda item: {
            "total_documents": 0,
            "satisfied_documents": 0,
            "pending_documents": 0,
            "mandatory_total": 0,
            "mandatory_satisfied": 0,
            "mandatory_missing": 0,
            "rejected_count": 0,
            "expired_count": 0,
            "pending_acceptance_count": 0,
            "ready_for_review": ready,
            "readiness_state": "READY" if ready else "PENDING",
            "health_score": 100 if ready else 0,
            "blockers": [],
        },
    )


# ---------------------------------------------------------------- TEST B. effective display status
@pytest.mark.django_db
def test_effective_status_reflects_mudra_business_stage_post_review(monkeypatch):
    _patch_dependencies(monkeypatch)
    service = _service()
    steps = _steps(service)
    owner = _employee(OWNER, "MudraOwner")
    reviewer = _employee(REVIEWER, "MudraReviewer")
    client = HttpClient()

    work = _real_review_approved_mudra_work(client, service, owner, reviewer)

    detail = client.get(f"/api/v1/work-items/{work.id}/", **_headers(OWNER))
    assert detail.status_code == 200, detail.content
    body = detail.json()
    assert body["status"] == "IN_PROGRESS"
    # The configured ServiceProcessStep.name for CREDIT_ELIGIBILITY - in this
    # test fixture that is code.replace("_", " ").title() (see _step()
    # above); production configuration may use a different display string
    # ("Credit & Eligibility"), but get_effective_status reads whatever name
    # is actually configured, so this proves the mechanism, not a hardcoded
    # label.
    expected_name = steps["CREDIT_ELIGIBILITY"].name
    assert body["effective_status"] == expected_name
    assert body["effective_status"] != "IN_PROGRESS"


@pytest.mark.django_db
def test_effective_status_preserves_review_and_rework_control_states():
    from contexts.work.models import WorkItem

    service = _service()
    steps = _steps(service)
    owner = _employee(OWNER, "MudraOwner")
    reviewer = _employee(REVIEWER, "MudraReviewer")
    client = HttpClient()

    work = _work(service, owner)
    WorkItem.objects.filter(tenant_id=TENANT, id=work.id).update(
        status="READY_FOR_REVIEW", reviewer_user_id=reviewer.id,
    )
    _seed_state(work, steps["APPLICATION"])

    res = client.get(f"/api/v1/work-items/{work.id}/", **_headers(OWNER))
    assert res.status_code == 200, res.content
    assert res.json()["effective_status"] == "READY_FOR_REVIEW"

    WorkItem.objects.filter(tenant_id=TENANT, id=work.id).update(
        status="REWORK_REQUIRED",
    )
    res2 = client.get(f"/api/v1/work-items/{work.id}/", **_headers(OWNER))
    assert res2.status_code == 200, res2.content
    assert res2.json()["effective_status"] == "REWORK_REQUIRED"


# ---------------------------------------------------------------- TEST C. Work Health post-review
@pytest.mark.django_db
def test_work_health_never_recommends_submit_for_review_post_mudra_approval(monkeypatch):
    _patch_dependencies(monkeypatch)
    _patch_work_health_document_readiness(monkeypatch, ready=True)
    service = _service()
    steps = _steps(service)
    owner = _employee(OWNER, "MudraOwner")
    reviewer = _employee(REVIEWER, "MudraReviewer")
    client = HttpClient()

    work = _real_review_approved_mudra_work(client, service, owner, reviewer)

    res = client.get(f"/api/v1/work-items/{work.id}/health/", **_headers(OWNER))
    assert res.status_code == 200, res.content
    next_action = res.json()["next_action"]
    assert next_action["code"] != "SUBMIT_FOR_REVIEW"
    assert next_action["code"] == "CONTINUE_MUDRA_CREDIT_ELIGIBILITY"
    assert next_action["label"] == "Complete Credit & Eligibility"


# ---------------------------------------------------------------- TEST D. generic Work isolation
@pytest.mark.django_db
def test_generic_work_health_submit_for_review_unaffected(monkeypatch):
    from contexts.work.models import WorkItem

    _patch_work_health_document_readiness(monkeypatch, ready=True)
    owner = _employee(OWNER, "GenericOwner")
    reviewer = _employee(REVIEWER, "GenericReviewer")
    client = HttpClient()

    # A plain generic Work item - no service at all.
    work = WorkItem.objects.create(
        tenant_id=TENANT, created_by=CREATOR, updated_by=CREATOR,
        title="Generic Task", client_id=uuid.uuid4(), service_id=None,
        owner_user_id=owner.id, reviewer_user_id=reviewer.id,
        priority="NORMAL", status="IN_PROGRESS",
    )

    res = client.get(f"/api/v1/work-items/{work.id}/health/", **_headers(OWNER))
    assert res.status_code == 200, res.content
    assert res.json()["next_action"]["code"] == "SUBMIT_FOR_REVIEW"
    assert res.json()["next_action"]["label"] == "Submit work for review"


# ---------------------------------------------------------------- TEST G. review re-entry blocked post-approval
@pytest.mark.django_db
def test_submit_for_review_still_blocked_after_mudra_approval(monkeypatch):
    _patch_dependencies(monkeypatch)
    service = _service()
    steps = _steps(service)
    owner = _employee(OWNER, "MudraOwner")
    reviewer = _employee(REVIEWER, "MudraReviewer")
    client = HttpClient()

    work = _real_review_approved_mudra_work(client, service, owner, reviewer)
    # Confirm the case has genuinely advanced past APPLICATION first.
    assert _state(work).current_step_id == steps["CREDIT_ELIGIBILITY"].id

    reentry = _post(client, work, "submit_for_review", {})
    assert reentry.status_code == 409
    assert reentry.json().get("code") == "MUDRA_INTERNAL_REVIEW_ALREADY_COMPLETED"
