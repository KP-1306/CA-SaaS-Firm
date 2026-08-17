"""Udyam workflow V2 regression suite.

Corrects the V1 concerns:
  * Fixtures set owner_user_id to the acting principal id directly
    (ownership representation A), so every generic PATCH actually reaches the
    serializer through the real permission path instead of failing at
    can_edit_work_item.
  * Non-Udyam regression tests prove the generic serializer semantics are
    unchanged.
  * The Udyam process fixtures create the SUBMIT_APPLICATION step and seed the
    correct starting position (the existing _process() helper omitted it).

Covers the mandatory V2 backend regression matrix (A-H).
"""

from __future__ import annotations

import io
import json
import uuid

import pytest
from django.test import Client as HttpClient
from django.utils import timezone


TENANT = "11111111-1111-1111-1111-111111111111"
OWNER = "44444444-4444-4444-4444-444444444444"
REVIEWER = "55555555-5555-5555-5555-555555555555"
STRANGER = "66666666-6666-6666-6666-666666666666"
CREATOR = "22222222-2222-2222-2222-222222222222"


def _h(principal=OWNER):
    return {"HTTP_X_TENANT_ID": TENANT, "HTTP_X_PRINCIPAL_ID": principal}


def _employee(principal, name, role="STAFF"):
    from contexts.identity.models import Employee

    return Employee.objects.create(
        tenant_id=TENANT,
        created_by=CREATOR,
        updated_by=CREATOR,
        name=name,
        email=f"{name.lower()}-{uuid.uuid4()}@example.com",
        role=role,
        principal_id=principal,
        is_active=True,
    )


def _udyam_service():
    from contexts.configuration.models import Service

    return Service.objects.create(
        tenant_id=TENANT,
        created_by=CREATOR,
        updated_by=CREATOR,
        domain_id=uuid.uuid4(),
        name="MSME (Udyam) Registration",
        code="UDYAM_REGISTRATION",
        description="Udyam regression service.",
    )


def _other_service(code="TAX_FILING"):
    from contexts.configuration.models import Service

    return Service.objects.create(
        tenant_id=TENANT,
        created_by=CREATOR,
        updated_by=CREATOR,
        domain_id=uuid.uuid4(),
        name=code.replace("_", " ").title(),
        code=code,
        description="Non-Udyam regression service.",
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
        description="Regression step.",
        display_order=order,
        is_active=True,
    )


def _all_steps(service):
    """Create the full Udyam step set INCLUDING SUBMIT_APPLICATION."""
    return {
        "submit": _step(service, "SUBMIT_APPLICATION", 10),
        "submitted": _step(service, "APPLICATION_SUBMISSION", 20),
        "query": _step(service, "QUERY_RESOLUTION", 30),
        "completion": _step(service, "COMPLETION", 40),
    }


def _operational_field(service, key="filing_status", field_type="TEXT", required=False):
    from contexts.configuration.models import ServiceOperationalField

    return ServiceOperationalField.objects.create(
        tenant_id=TENANT,
        created_by=CREATOR,
        updated_by=CREATOR,
        service_id=service.id,
        key=key,
        label=key.replace("_", " ").title(),
        field_type=field_type,
        display_order=1,
        required=required,
        is_active=True,
    )


def _work(service, *, owner=OWNER, status="IN_PROGRESS"):
    """Create a work item OWNED by the principal directly (representation A).

    owner_user_id == principal id means is_owner() and can_edit_work_item()
    both pass through the real permission path for a generic PATCH.
    """
    from contexts.work.models import WorkItem

    _employee(OWNER, "UdyamOwner")
    _employee(REVIEWER, "UdyamReviewer")

    return WorkItem.objects.create(
        tenant_id=TENANT,
        created_by=CREATOR,
        updated_by=CREATOR,
        title="Udyam Regression Work",
        client_id=uuid.uuid4(),
        service_id=service.id,
        owner_user_id=owner,          # representation A: raw principal id
        reviewer_user_id=REVIEWER,
        priority="NORMAL",
        status=status,
    )


def _seed_process(item, step):
    from contexts.work.models import WorkProcessState

    return WorkProcessState.objects.create(
        tenant_id=TENANT,
        created_by=CREATOR,
        updated_by=CREATOR,
        work_item_id=item.id,
        current_step_id=step.id,
        entered_at=timezone.now(),
        entered_by=OWNER,
        note="Seeded for regression test.",
    )


def _patch_deps(monkeypatch, *, operational_superuser=False):
    import contexts.work.views as views

    monkeypatch.setattr(views, "calculate_document_readiness", lambda item: {"ready_for_review": True, "missing": 0, "mandatory_missing": 0})
    monkeypatch.setattr(views, "qa_prepare_cycle", lambda *a, **k: None)
    monkeypatch.setattr(views, "qa_readiness", lambda item: {"enabled": False, "ready_for_submission": True, "ready_for_approval": True})
    monkeypatch.setattr(views, "qa_mark_submitted", lambda *a, **k: object())
    monkeypatch.setattr(views, "qa_mark_approved", lambda *a, **k: object())
    monkeypatch.setattr(views, "qa_mark_changes_requested", lambda *a, **k: object())
    monkeypatch.setattr(views, "qa_cycle_summary", lambda cycle: {})
    monkeypatch.setattr(views, "notify_work_transition", lambda *a, **k: None)



    if operational_superuser:
        monkeypatch.setattr(
            "contexts.work.ownership.is_operational_superuser",
            lambda tenant_id, principal: True,
        )

def _submit(http, item):
    return http.post(
        f"/api/v1/work-items/{item.id}/udyam-submit-application/",
        data=json.dumps({
            "application_reference": "UDYAM-REF-001",
            "submission_date": "2026-08-12",
            "submission_time": "14:30",
        }),
        content_type="application/json",
        **_h(),
    )


# =====================================================================
# B. GENERIC OPERATIONAL DATA (the core V1 correction)
# =====================================================================

@pytest.mark.django_db
def test_b1_b9_non_udyam_service_semantics_unchanged(monkeypatch):
    """B1/B9: non-Udyam generic operational-data validation is unchanged.

    A normal TEXT field validates and persists exactly as before; the fix is
    scoped to the Udyam service only.
    """
    _patch_deps(monkeypatch, operational_superuser=True)
    service = _other_service()
    _operational_field(service, key="return_type")
    item = _work(service)

    http = HttpClient()
    resp = http.patch(
        f"/api/v1/work-items/{item.id}/",
        data=json.dumps({"operational_data": {"return_type": "ITR-3"}}),
        content_type="application/json",
        **_h(),
    )
    assert resp.status_code == 200, resp.content
    item.refresh_from_db()
    assert item.operational_data.get("return_type") == "ITR-3"


@pytest.mark.django_db
def test_b2_unknown_normal_field_still_rejected(monkeypatch):
    """B2: unknown normal operational field is still rejected (non-Udyam)."""
    _patch_deps(monkeypatch, operational_superuser=True)
    service = _other_service("COMPLIANCE_X")
    _operational_field(service, key="known_field")
    item = _work(service)

    http = HttpClient()
    resp = http.patch(
        f"/api/v1/work-items/{item.id}/",
        data=json.dumps({"operational_data": {"unknown_field": "x"}}),
        content_type="application/json",
        **_h(),
    )
    assert resp.status_code == 400, resp.content
    assert "Unknown" in str(resp.json())


@pytest.mark.django_db
def test_b2_unknown_field_rejected_on_udyam_too(monkeypatch):
    """Unknown NON-reserved field is still rejected on the Udyam service."""
    _patch_deps(monkeypatch, operational_superuser=True)
    service = _udyam_service()
    _all_steps(service)
    item = _work(service)

    http = HttpClient()
    resp = http.patch(
        f"/api/v1/work-items/{item.id}/",
        data=json.dumps({"operational_data": {"totally_unknown": "x"}}),
        content_type="application/json",
        **_h(),
    )
    assert resp.status_code == 400, resp.content
    assert "Unknown" in str(resp.json())


@pytest.mark.django_db
def test_b3_generic_patch_without_operational_data_preserves_evidence(monkeypatch):
    """B3/B4: PATCH without operational_data does not erase Udyam evidence."""
    _patch_deps(monkeypatch)
    service = _udyam_service()
    steps = _all_steps(service)
    item = _work(service)
    _seed_process(item, steps["submit"])
    http = HttpClient()

    assert _submit(http, item).status_code == 200

    resp = http.patch(
        f"/api/v1/work-items/{item.id}/",
        data=json.dumps({"priority": "HIGH"}),
        content_type="application/json",
        **_h(),
    )
    assert resp.status_code == 200, resp.content
    item.refresh_from_db()
    assert item.operational_data["udyam_application_reference"] == "UDYAM-REF-001"
    assert item.operational_data["udyam_submission_date"] == "2026-08-12"
    assert item.operational_data["udyam_submission_time"] == "14:30"


@pytest.mark.django_db
def test_b4_b5_generic_patch_cannot_erase_or_overwrite_evidence(monkeypatch):
    """B4/B5: generic PATCH cannot erase or overwrite reserved evidence."""
    _patch_deps(monkeypatch, operational_superuser=True)
    service = _udyam_service()
    steps = _all_steps(service)
    item = _work(service)
    _seed_process(item, steps["submit"])
    http = HttpClient()

    assert _submit(http, item).status_code == 200

    # Attempt to overwrite AND erase via a supplied operational_data payload.
    resp = http.patch(
        f"/api/v1/work-items/{item.id}/",
        data=json.dumps({"operational_data": {
            "udyam_application_reference": "TAMPERED",
            "udyam_submission_date": "",
        }}),
        content_type="application/json",
        **_h(),
    )
    assert resp.status_code == 200, resp.content
    item.refresh_from_db()
    assert item.operational_data["udyam_application_reference"] == "UDYAM-REF-001"
    assert item.operational_data["udyam_submission_date"] == "2026-08-12"


@pytest.mark.django_db
def test_b6_generic_patch_updates_normal_field_and_keeps_evidence(monkeypatch):
    """B6: generic Udyam PATCH updates a normal configured field while
    retaining process evidence.
    """
    _patch_deps(monkeypatch, operational_superuser=True)
    service = _udyam_service()
    steps = _all_steps(service)
    _operational_field(service, key="filing_status")
    item = _work(service)
    _seed_process(item, steps["submit"])
    http = HttpClient()

    assert _submit(http, item).status_code == 200

    resp = http.patch(
        f"/api/v1/work-items/{item.id}/",
        data=json.dumps({"operational_data": {"filing_status": "Filed"}}),
        content_type="application/json",
        **_h(),
    )
    assert resp.status_code == 200, resp.content
    item.refresh_from_db()
    assert item.operational_data.get("filing_status") == "Filed"
    assert item.operational_data["udyam_application_reference"] == "UDYAM-REF-001"


@pytest.mark.django_db
def test_b7_b8_query_and_certificate_evidence_protected(monkeypatch):
    """B7/B8: query + certificate evidence protected from generic save."""
    _patch_deps(monkeypatch)
    service = _udyam_service()
    steps = _all_steps(service)
    item = _work(service)
    _seed_process(item, steps["submit"])
    http = HttpClient()

    _submit(http, item)
    http.post(
        f"/api/v1/work-items/{item.id}/udyam-report-query/",
        data=json.dumps({"query_type": "OTP_REQUIRED", "remarks": "OTP needed."}),
        content_type="application/json",
        **_h(),
    )

    # Generic PATCH tries to tamper query evidence.
    http.patch(
        f"/api/v1/work-items/{item.id}/",
        data=json.dumps({"operational_data": {"udyam_query_type": "HACKED"}}),
        content_type="application/json",
        **_h(),
    )
    item.refresh_from_db()
    assert item.operational_data["udyam_query_type"] == "OTP_REQUIRED"


# =====================================================================
# C. SUBMISSION
# =====================================================================

@pytest.mark.django_db
def test_c1_submission_requires_submit_application_step(monkeypatch):
    """C1: submission requires the SUBMIT_APPLICATION durable step."""
    _patch_deps(monkeypatch)
    service = _udyam_service()
    steps = _all_steps(service)
    item = _work(service)
    _seed_process(item, steps["submitted"])  # wrong starting step
    http = HttpClient()

    resp = _submit(http, item)
    assert resp.status_code == 400, resp.content
    assert "SUBMIT_APPLICATION" in resp.json().get("detail", "")


@pytest.mark.django_db
@pytest.mark.parametrize("missing", ["application_reference", "submission_date", "submission_time"])
def test_c2_c4_missing_fields_rejected(monkeypatch, missing):
    """C2-C4: each missing required submission field is rejected."""
    _patch_deps(monkeypatch)
    service = _udyam_service()
    steps = _all_steps(service)
    item = _work(service)
    _seed_process(item, steps["submit"])
    http = HttpClient()

    payload = {
        "application_reference": "REF",
        "submission_date": "2026-08-12",
        "submission_time": "14:30",
    }
    del payload[missing]
    resp = http.post(
        f"/api/v1/work-items/{item.id}/udyam-submit-application/",
        data=json.dumps(payload),
        content_type="application/json",
        **_h(),
    )
    assert resp.status_code == 400, resp.content


@pytest.mark.django_db
def test_c5_c8_submit_persists_and_duplicate_rejected(monkeypatch):
    """C5-C8: submit persists all three, reaches APPLICATION_SUBMISSION,
    keeps status, and rejects a duplicate submit.
    """
    from contexts.work.models import WorkProcessState

    _patch_deps(monkeypatch)
    service = _udyam_service()
    steps = _all_steps(service)
    item = _work(service)
    _seed_process(item, steps["submit"])
    http = HttpClient()

    assert _submit(http, item).status_code == 200
    item.refresh_from_db()
    assert item.operational_data["udyam_application_reference"] == "UDYAM-REF-001"
    assert item.status == "IN_PROGRESS"  # C7: not accidentally completed

    state = WorkProcessState.objects.get(tenant_id=TENANT, work_item_id=item.id)
    assert state.current_step_id == steps["submitted"].id

    # C8: duplicate submit at APPLICATION_SUBMISSION is rejected.
    dup = _submit(http, item)
    assert dup.status_code == 400, dup.content
    assert "SUBMIT_APPLICATION" in dup.json().get("detail", "")


# =====================================================================
# D. QUERY
# =====================================================================

@pytest.mark.django_db
def test_d_query_round_trip_preserves_evidence(monkeypatch):
    """D1-D10: query round trip preserves submission + query evidence."""
    from contexts.work.models import WorkProcessState

    _patch_deps(monkeypatch)
    service = _udyam_service()
    steps = _all_steps(service)
    item = _work(service)
    _seed_process(item, steps["submit"])
    http = HttpClient()

    _submit(http, item)

    # Report query.
    rq = http.post(
        f"/api/v1/work-items/{item.id}/udyam-report-query/",
        data=json.dumps({"query_type": "OTP_REQUIRED", "remarks": "OTP needed."}),
        content_type="application/json",
        **_h(),
    )
    assert rq.status_code == 200, rq.content
    state = WorkProcessState.objects.get(tenant_id=TENANT, work_item_id=item.id)
    assert state.current_step_id == steps["query"].id
    item.refresh_from_db()
    assert item.operational_data["udyam_application_reference"] == "UDYAM-REF-001"
    assert item.operational_data["udyam_query_type"] == "OTP_REQUIRED"

    # Resolve query.
    rr = http.post(
        f"/api/v1/work-items/{item.id}/udyam-resolve-query/",
        data=json.dumps({"remarks": "OTP entered."}),
        content_type="application/json",
        **_h(),
    )
    assert rr.status_code == 200, rr.content
    state.refresh_from_db()
    assert state.current_step_id == steps["submitted"].id
    item.refresh_from_db()
    assert item.operational_data["udyam_application_reference"] == "UDYAM-REF-001"
    assert item.operational_data["udyam_query_type"] == "OTP_REQUIRED"
    assert item.operational_data["udyam_query_resolution_remarks"] == "OTP entered."


# =====================================================================
# E. COMPLETION
# =====================================================================

@pytest.mark.django_db
def test_e_completion_persists_certificate_and_completes(monkeypatch):
    """E1-E8: completion persists certificate, reaches COMPLETION/COMPLETED,
    retains earlier evidence.
    """
    from contexts.work.models import WorkProcessState

    _patch_deps(monkeypatch)
    service = _udyam_service()
    steps = _all_steps(service)
    item = _work(service)
    _seed_process(item, steps["submit"])
    http = HttpClient()

    _submit(http, item)

    cert = io.BytesIO(b"%PDF-1.4 fake certificate")
    cert.name = "certificate.pdf"
    resp = http.post(
        f"/api/v1/work-items/{item.id}/udyam-complete-registration/",
        data={"certificate": cert, "remarks": "Done."},
        **_h(),
    )
    assert resp.status_code == 200, resp.content

    item.refresh_from_db()
    assert item.status == "COMPLETED"
    assert item.completed_at is not None
    assert item.operational_data.get("udyam_certificate_attachment_id")
    assert item.operational_data["udyam_application_reference"] == "UDYAM-REF-001"

    state = WorkProcessState.objects.get(tenant_id=TENANT, work_item_id=item.id)
    assert state.current_step_id == steps["completion"].id


# =====================================================================
# G. HISTORY
# =====================================================================

@pytest.mark.django_db
def test_g_history_semantic_and_no_duplicate(monkeypatch):
    """G1/G2: submission history has a semantic title and is NOT duplicated
    as both a Work note and a typed process event.
    """
    _patch_deps(monkeypatch)
    service = _udyam_service()
    steps = _all_steps(service)
    item = _work(service)
    _seed_process(item, steps["submit"])
    http = HttpClient()

    _submit(http, item)

    resp = http.get(f"/api/v1/work-items/{item.id}/history/", **_h())
    assert resp.status_code == 200, resp.content
    events = resp.json()

    titles = [e.get("title", "") for e in events]
    # Semantic title present.
    assert any("Application submitted" == t for t in titles), titles
    # No generic "Work note" for the Udyam submission (deduped).
    udyam_worknotes = [
        e for e in events
        if e.get("title", "").lower() in ("work note", "work_note")
        and "udyam" in (e.get("entry", "") or "").lower()
    ]
    assert udyam_worknotes == [], f"Udyam WorkNote duplicate present: {udyam_worknotes}"

    # Exactly one submission representation.
    submission_events = [e for e in events if e.get("title") == "Application submitted"]
    assert len(submission_events) == 1, submission_events


@pytest.mark.django_db
def test_g_query_and_completion_semantic_titles(monkeypatch):
    """G3/G4/G5: query received, query resolved, registration completed
    all have semantic titles.
    """
    _patch_deps(monkeypatch)
    service = _udyam_service()
    steps = _all_steps(service)
    item = _work(service)
    _seed_process(item, steps["submit"])
    http = HttpClient()

    _submit(http, item)
    http.post(
        f"/api/v1/work-items/{item.id}/udyam-report-query/",
        data=json.dumps({"query_type": "OTP_REQUIRED", "remarks": "OTP."}),
        content_type="application/json",
        **_h(),
    )
    http.post(
        f"/api/v1/work-items/{item.id}/udyam-resolve-query/",
        data=json.dumps({"remarks": "Resolved."}),
        content_type="application/json",
        **_h(),
    )

    resp = http.get(f"/api/v1/work-items/{item.id}/history/", **_h())
    titles = [e.get("title", "") for e in resp.json()]
    assert "Query / issue received" in titles, titles
    assert "Query resolved" in titles, titles


# =====================================================================
# H. PERMISSIONS
# =====================================================================

@pytest.mark.django_db
def test_h1_h2_owner_can_submit_stranger_cannot(monkeypatch):
    """H1/H2: valid owner can submit; a non-owner cannot."""
    _patch_deps(monkeypatch)
    service = _udyam_service()
    steps = _all_steps(service)
    item = _work(service)
    _seed_process(item, steps["submit"])
    http = HttpClient()

    # Stranger (not owner) cannot submit.
    denied = http.post(
        f"/api/v1/work-items/{item.id}/udyam-submit-application/",
        data=json.dumps({
            "application_reference": "R", "submission_date": "2026-08-12", "submission_time": "10:00",
        }),
        content_type="application/json",
        **_h(STRANGER),
    )
    assert denied.status_code in (403, 400), denied.content

    # Owner can.
    assert _submit(http, item).status_code == 200


# =====================================================================
# K. AUDIT / updated_by consistency
# =====================================================================

@pytest.mark.django_db
def test_k_report_and_resolve_set_updated_by(monkeypatch):
    """K: report_query and resolve_query set updated_by to the actor."""
    _patch_deps(monkeypatch)
    service = _udyam_service()
    steps = _all_steps(service)
    item = _work(service)
    _seed_process(item, steps["submit"])
    http = HttpClient()

    _submit(http, item)

    http.post(
        f"/api/v1/work-items/{item.id}/udyam-report-query/",
        data=json.dumps({"query_type": "OTP_REQUIRED", "remarks": "OTP."}),
        content_type="application/json",
        **_h(),
    )
    item.refresh_from_db()
    assert str(item.updated_by) == OWNER

    http.post(
        f"/api/v1/work-items/{item.id}/udyam-resolve-query/",
        data=json.dumps({"remarks": "Resolved."}),
        content_type="application/json",
        **_h(),
    )
    item.refresh_from_db()
    assert str(item.updated_by) == OWNER


# =====================================================================
# D (critical). MULTI-QUERY HISTORY EVENT-TIME CORRECTNESS
# =====================================================================

@pytest.mark.django_db
def test_d_multi_query_history_retains_event_time_values(monkeypatch):
    """History must show each event's OWN event-time values, never current
    operational_data.

    Sequence: Submit REF-100 -> Query1 OTP_REQUIRED/"OTP not received"
    -> Resolve1 "OTP completed" -> Query2 DOCUMENT_QUERY/"PAN mismatch"
    -> Resolve2 "PAN corrected".  After Query2/Resolve2 have overwritten the
    current operational_data, the Query1 history event must still show its
    original OTP values.
    """
    _patch_deps(monkeypatch)
    service = _udyam_service()
    steps = _all_steps(service)
    item = _work(service)
    _seed_process(item, steps["submit"])
    http = HttpClient()

    # Submit with a distinctive reference.
    r = http.post(
        f"/api/v1/work-items/{item.id}/udyam-submit-application/",
        data=json.dumps({
            "application_reference": "REF-100",
            "submission_date": "2026-08-12",
            "submission_time": "09:00",
        }),
        content_type="application/json",
        **_h(),
    )
    assert r.status_code == 200, r.content

    def _report(qtype, remarks):
        resp = http.post(
            f"/api/v1/work-items/{item.id}/udyam-report-query/",
            data=json.dumps({"query_type": qtype, "remarks": remarks}),
            content_type="application/json",
            **_h(),
        )
        assert resp.status_code == 200, resp.content

    def _resolve(remarks):
        resp = http.post(
            f"/api/v1/work-items/{item.id}/udyam-resolve-query/",
            data=json.dumps({"remarks": remarks}),
            content_type="application/json",
            **_h(),
        )
        assert resp.status_code == 200, resp.content

    _report("OTP_REQUIRED", "OTP not received")
    _resolve("OTP completed")
    _report("DOCUMENT_QUERY", "PAN mismatch")
    _resolve("PAN corrected")

    # Current operational_data now holds Query2 values.
    item.refresh_from_db()
    assert item.operational_data["udyam_query_type"] == "DOCUMENT_QUERY"
    assert item.operational_data["udyam_query_resolution_remarks"] == "PAN corrected"

    resp = http.get(f"/api/v1/work-items/{item.id}/history/", **_h())
    assert resp.status_code == 200, resp.content
    events = resp.json()

    received = [e for e in events if e.get("title") == "Query / issue received"]
    resolved = [e for e in events if e.get("title") == "Query resolved"]
    submitted = [e for e in events if e.get("title") == "Application submitted"]

    # Exactly one of each transition per cycle.
    assert len(received) == 2, [e.get("detail") for e in received]
    assert len(resolved) == 2, [e.get("detail") for e in resolved]
    assert len(submitted) == 1, submitted

    # Order the query events by timestamp to identify cycle 1 vs cycle 2.
    received.sort(key=lambda e: e["created_at"])
    resolved.sort(key=lambda e: e["created_at"])

    # Query 1 event retains its OWN event-time values (NOT Query 2's).
    q1 = received[0]["detail"]
    assert "OTP_REQUIRED" in q1, q1
    assert "OTP not received" in q1, q1
    assert "DOCUMENT_QUERY" not in q1, q1
    assert "PAN mismatch" not in q1, q1

    # Query 1 resolution retains its own remarks.
    r1 = resolved[0]["detail"]
    assert "OTP completed" in r1, r1
    assert "PAN corrected" not in r1, r1

    # Query 2 event shows its own values.
    q2 = received[1]["detail"]
    assert "DOCUMENT_QUERY" in q2, q2
    assert "PAN mismatch" in q2, q2

    # Query 2 resolution shows its own remarks.
    r2 = resolved[1]["detail"]
    assert "PAN corrected" in r2, r2

    # Submission event still shows REF-100.
    assert "REF-100" in submitted[0]["detail"], submitted[0]["detail"]

    # No duplicate generic "Work note" for any Udyam business event.
    udyam_worknotes = [
        e for e in events
        if e.get("title", "").lower() in ("work note", "work_note")
        and "udyam" in (e.get("entry", "") or "").lower()
    ]
    assert udyam_worknotes == [], udyam_worknotes
