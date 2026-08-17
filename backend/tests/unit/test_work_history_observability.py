from types import SimpleNamespace

from contexts.work.history_observability import (
    capture_work_snapshot,
    dependency_impact,
    diagnostic_event_payload,
    diff_snapshots,
    evaluate_dependency_contract,
    evaluate_udyam_invariants,
    failed_invariants,
    monitored_udyam_data,
    sanitize,
)


def _work(**overrides):
    values = {
        "id": "work-1",
        "tenant_id": "tenant-1",
        "service_id": "service-1",
        "status": "IN_PROGRESS",
        "owner_user_id": "owner-1",
        "reviewer_user_id": "reviewer-1",
        "row_version": 7,
        "updated_at": "2026-08-13T11:31:00Z",
        "operational_data": {},
    }

    values.update(overrides)

    return SimpleNamespace(**values)


def test_snapshot_keeps_only_monitored_udyam_evidence():
    work = _work(
        operational_data={
            "udyam_application_reference": "REF-1",
            "udyam_submission_date": "2026-08-13",
            "udyam_submission_time": "17:00",
            "unrelated_field": "do not project",
        }
    )

    snapshot = capture_work_snapshot(
        work_item=work,
        process_step_code="APPLICATION_SUBMISSION",
        process_step_id="step-1",
    )

    assert snapshot["udyam"][
        "udyam_application_reference"
    ] == "REF-1"

    assert "unrelated_field" not in snapshot["udyam"]


def test_snapshot_diff_identifies_exact_lost_submission_evidence():
    before = capture_work_snapshot(
        work_item=_work(
            row_version=8,
            operational_data={
                "udyam_application_reference": "35353",
                "udyam_submission_date": "2026-08-12",
                "udyam_submission_time": "20:04",
            },
        ),
        process_step_code="APPLICATION_SUBMISSION",
    )

    after = capture_work_snapshot(
        work_item=_work(
            row_version=9,
            operational_data={},
        ),
        process_step_code="APPLICATION_SUBMISSION",
    )

    changes = diff_snapshots(
        before,
        after,
    )

    assert changes[
        "udyam.udyam_application_reference"
    ] == {
        "before": "35353",
        "after": None,
    }

    assert changes[
        "udyam.udyam_submission_date"
    ] == {
        "before": "2026-08-12",
        "after": None,
    }

    assert changes[
        "udyam.udyam_submission_time"
    ] == {
        "before": "20:04",
        "after": None,
    }


def test_application_submission_invariant_detects_missing_identity():
    results = evaluate_udyam_invariants(
        work_status="IN_PROGRESS",
        process_step_code="APPLICATION_SUBMISSION",
        operational_data={},
    )

    failed = failed_invariants(results)

    fields = {
        item["field"]
        for item in failed
    }

    assert fields == {
        "udyam_application_reference",
        "udyam_submission_date",
        "udyam_submission_time",
    }


def test_application_submission_invariant_passes_when_identity_exists():
    results = evaluate_udyam_invariants(
        work_status="IN_PROGRESS",
        process_step_code="APPLICATION_SUBMISSION",
        operational_data={
            "udyam_application_reference": "35353",
            "udyam_submission_date": "2026-08-12",
            "udyam_submission_time": "20:04",
        },
    )

    assert failed_invariants(results) == []


def test_query_resolution_requires_submission_and_query_context():
    results = evaluate_udyam_invariants(
        work_status="IN_PROGRESS",
        process_step_code="QUERY_RESOLUTION",
        operational_data={
            "udyam_application_reference": "REF",
            "udyam_submission_date": "2026-08-12",
            "udyam_submission_time": "20:04",
            "udyam_query_type": "",
            "udyam_query_remarks": "",
        },
    )

    failed = failed_invariants(results)

    assert {
        item["field"]
        for item in failed
    } == {
        "udyam_query_type",
        "udyam_query_remarks",
    }


def test_completion_requires_certificate_and_completed_status():
    results = evaluate_udyam_invariants(
        work_status="IN_PROGRESS",
        process_step_code="COMPLETION",
        operational_data={
            "udyam_application_reference": "REF",
            "udyam_submission_date": "2026-08-12",
            "udyam_submission_time": "20:04",
        },
    )

    failed = failed_invariants(results)

    fields = {
        item["field"]
        for item in failed
    }

    assert "udyam_certificate_attachment_id" in fields
    assert "work.status" in fields


def test_submit_dependency_requires_submit_application_step():
    result = evaluate_dependency_contract(
        "UDYAM_SUBMIT_APPLICATION",
        work_status="IN_PROGRESS",
        process_step_code="INTERNAL_REVIEW",
    )

    process_check = next(
        row
        for row in result
        if row["dependency"] == "process.current_step"
    )

    assert process_check["passed"] is False
    assert process_check["expected"] == "SUBMIT_APPLICATION"
    assert process_check["actual"] == "INTERNAL_REVIEW"


def test_dependency_impact_explains_submission_evidence_consumers():
    impact = dependency_impact(
        {
            "udyam.udyam_application_reference": {
                "before": "REF",
                "after": None,
            }
        }
    )

    assert "Query cycle" in impact
    assert "Completion evidence" in impact
    assert "Udyam state integrity" in impact


def test_sensitive_values_are_redacted():
    result = sanitize(
        {
            "token": "secret-token",
            "otp": "123456",
            "safe": "hello",
        }
    )

    assert result["token"] == "[REDACTED]"
    assert result["otp"] == "[REDACTED]"
    assert result["safe"] == "hello"


def test_file_values_store_metadata_not_content():
    upload = SimpleNamespace(
        name="certificate.pdf",
        content_type="application/pdf",
        size=1234,
        read=lambda: b"DO NOT STORE THIS",
    )

    result = sanitize(
        {
            "certificate": upload,
        }
    )

    assert result["certificate"] == {
        "file_name": "certificate.pdf",
        "content_type": "application/pdf",
        "size": 1234,
    }


def test_diagnostic_payload_contains_dependency_and_invariant_evidence():
    before = capture_work_snapshot(
        work_item=_work(
            row_version=8,
            operational_data={
                "udyam_application_reference": "35353",
                "udyam_submission_date": "2026-08-12",
                "udyam_submission_time": "20:04",
            },
        ),
        process_step_code="APPLICATION_SUBMISSION",
    )

    after = capture_work_snapshot(
        work_item=_work(
            row_version=9,
            operational_data={},
        ),
        process_step_code="APPLICATION_SUBMISSION",
    )

    payload = diagnostic_event_payload(
        action="WORK_GENERIC_UPDATE",
        result="SUCCESS",
        before=before,
        after=after,
        work_status="IN_PROGRESS",
        process_step_code="APPLICATION_SUBMISSION",
        correlation_id="corr-1",
    )

    assert payload["correlation_id"] == "corr-1"

    assert (
        "udyam.udyam_application_reference"
        in payload["changes"]
    )

    assert payload["invariant_failures"]

    assert (
        "Udyam state integrity"
        in payload["downstream_dependents"]
    )
