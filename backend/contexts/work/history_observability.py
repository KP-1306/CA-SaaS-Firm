"""Work-domain observability and dependency contracts.

This module is intentionally NOT a workflow engine.

Authoritative business state remains in:
- WorkItem
- WorkProcessState
- configured ServiceProcessStep
- document/QA/assignment domain models

This module only:
- captures controlled snapshots,
- calculates before/after diffs,
- describes dependencies,
- evaluates postconditions/invariants,
- describes downstream dependency impact,
- sanitizes diagnostic evidence.

It performs no database writes.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Mapping


# ---------------------------------------------------------------------
# Monitored Udyam evidence
# ---------------------------------------------------------------------

UDYAM_MONITORED_KEYS = (
    "udyam_application_reference",
    "udyam_submission_date",
    "udyam_submission_time",
    "udyam_query_type",
    "udyam_query_remarks",
    "udyam_query_resolution_remarks",
    "udyam_certificate_attachment_id",
)


# Never expose secret-like values in diagnostic history.
_REDACT_KEYS = frozenset(
    {
        "password",
        "token",
        "access_token",
        "refresh_token",
        "authorization",
        "cookie",
        "session",
        "sessionid",
        "otp",
        "otp_code",
        "secret",
        "client_secret",
        "api_key",
    }
)


@dataclass(frozen=True)
class DependencyContract:
    action: str
    required_process_step: str | None
    allowed_work_statuses: tuple[str, ...]
    reads: tuple[str, ...]
    writes: tuple[str, ...]
    invariants: tuple[str, ...]
    downstream_dependents: tuple[str, ...]


# ---------------------------------------------------------------------
# Canonical Udyam dependency contracts
#
# IMPORTANT:
# These describe existing behavior.
# They do not implement or authorize transitions.
# ---------------------------------------------------------------------

UDYAM_ACTION_CONTRACTS: dict[str, DependencyContract] = {
    "UDYAM_SUBMIT_APPLICATION": DependencyContract(
        action="UDYAM_SUBMIT_APPLICATION",
        required_process_step="SUBMIT_APPLICATION",
        allowed_work_statuses=("IN_PROGRESS",),
        reads=(
            "WorkItem.status",
            "WorkItem.owner_user_id",
            "WorkItem.service_id",
            "WorkItem.operational_data",
            "WorkProcessState.current_step_id",
            "ServiceProcessStep",
        ),
        writes=(
            "WorkItem.operational_data.udyam_application_reference",
            "WorkItem.operational_data.udyam_submission_date",
            "WorkItem.operational_data.udyam_submission_time",
            "WorkItem.updated_by",
            "WorkItem.row_version",
            "WorkProcessState.current_step_id",
            "WorkProcessState.entered_at",
            "WorkNote",
            "AuditEvent",
        ),
        invariants=(
            "UDYAM_SUBMISSION_IDENTITY_PRESENT",
            "UDYAM_PROCESS_APPLICATION_SUBMISSION",
        ),
        downstream_dependents=(
            "UdyamProcessPanel",
            "WorkHealth",
            "effective_status",
            "Udyam query flow",
            "Udyam completion flow",
            "History",
        ),
    ),

    "UDYAM_REPORT_QUERY": DependencyContract(
        action="UDYAM_REPORT_QUERY",
        required_process_step="APPLICATION_SUBMISSION",
        allowed_work_statuses=("IN_PROGRESS",),
        reads=(
            "WorkItem.status",
            "WorkItem.owner_user_id",
            "WorkItem.operational_data",
            "WorkProcessState.current_step_id",
        ),
        writes=(
            "WorkItem.operational_data.udyam_query_type",
            "WorkItem.operational_data.udyam_query_remarks",
            "WorkItem.operational_data.udyam_query_resolution_remarks",
            "WorkProcessState.current_step_id",
            "WorkNote",
            "AuditEvent",
        ),
        invariants=(
            "UDYAM_SUBMISSION_IDENTITY_PRESENT",
            "UDYAM_QUERY_CONTEXT_PRESENT",
            "UDYAM_PROCESS_QUERY_RESOLUTION",
        ),
        downstream_dependents=(
            "UdyamProcessPanel",
            "Query Resolution",
            "WorkHealth",
            "effective_status",
            "History",
        ),
    ),

    "UDYAM_RESOLVE_QUERY": DependencyContract(
        action="UDYAM_RESOLVE_QUERY",
        required_process_step="QUERY_RESOLUTION",
        allowed_work_statuses=("IN_PROGRESS",),
        reads=(
            "WorkItem.status",
            "WorkItem.owner_user_id",
            "WorkItem.operational_data",
            "WorkProcessState.current_step_id",
        ),
        writes=(
            "WorkItem.operational_data.udyam_query_resolution_remarks",
            "WorkProcessState.current_step_id",
            "WorkNote",
            "AuditEvent",
        ),
        invariants=(
            "UDYAM_SUBMISSION_IDENTITY_PRESENT",
            "UDYAM_QUERY_CONTEXT_PRESENT",
            "UDYAM_QUERY_RESPONSE_PRESENT",
            "UDYAM_PROCESS_APPLICATION_SUBMISSION",
        ),
        downstream_dependents=(
            "UdyamProcessPanel",
            "Application Submitted",
            "WorkHealth",
            "effective_status",
            "History",
        ),
    ),

    "UDYAM_COMPLETE_REGISTRATION": DependencyContract(
        action="UDYAM_COMPLETE_REGISTRATION",
        required_process_step="APPLICATION_SUBMISSION",
        allowed_work_statuses=("IN_PROGRESS",),
        reads=(
            "WorkItem.status",
            "WorkItem.owner_user_id",
            "WorkItem.operational_data",
            "WorkProcessState.current_step_id",
            "certificate upload",
        ),
        writes=(
            "DocumentAttachment",
            "WorkItem.operational_data.udyam_certificate_attachment_id",
            "WorkItem.status",
            "WorkItem.completed_at",
            "WorkProcessState.current_step_id",
            "WorkNote",
            "AuditEvent",
        ),
        invariants=(
            "UDYAM_SUBMISSION_IDENTITY_PRESENT",
            "UDYAM_CERTIFICATE_PRESENT",
            "UDYAM_PROCESS_COMPLETION",
            "WORK_COMPLETED",
        ),
        downstream_dependents=(
            "Certificate download",
            "Udyam terminal panel",
            "WorkHealth",
            "effective_status",
            "Work grid",
            "History",
        ),
    ),

    # Diagnostic contract for the generic Work update path.
    # This is intentionally not Udyam-specific workflow logic.
    "WORK_GENERIC_UPDATE": DependencyContract(
        action="WORK_GENERIC_UPDATE",
        required_process_step=None,
        allowed_work_statuses=(
            "NOT_STARTED",
            "IN_PROGRESS",
            "REWORK_REQUIRED",
        ),
        reads=(
            "WorkItem.status",
            "WorkItem.owner_user_id",
            "request.data",
            "WorkItem.operational_data",
            "ownership.can_edit_work_item",
            "ownership.is_operational_superuser",
        ),
        writes=(
            "WorkItem serializer writable fields",
        ),
        invariants=(
            "UDYAM_DURABLE_EVIDENCE_NOT_ERASED",
        ),
        downstream_dependents=(
            "Work drawer",
            "Work grid",
            "permissions",
            "effective_status",
            "Udyam process UI",
            "History",
        ),
    ),
}


# ---------------------------------------------------------------------
# Snapshot helpers
# ---------------------------------------------------------------------

def _as_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _clean_mapping(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    return dict(value)


def sanitize(value: Any, *, key: str = "") -> Any:
    """Return safe diagnostic content without secrets or file bodies."""

    key_l = str(key or "").lower()

    if key_l in _REDACT_KEYS:
        return "[REDACTED]"

    if isinstance(value, Mapping):
        result = {}

        for child_key, child_value in value.items():
            child_name = str(child_key)

            result[child_name] = sanitize(
                child_value,
                key=child_name,
            )

        return result

    if isinstance(value, (list, tuple)):
        return [
            sanitize(item)
            for item in value
        ]

    # Uploaded-file-like values must never be serialized into history.
    if hasattr(value, "read") and hasattr(value, "name"):
        return {
            "file_name": _as_text(
                getattr(value, "name", "")
            ),
            "content_type": _as_text(
                getattr(value, "content_type", "")
            ),
            "size": getattr(value, "size", None),
        }

    return deepcopy(value)


def monitored_udyam_data(
    operational_data: Mapping[str, Any] | None,
) -> dict[str, Any]:
    source = _clean_mapping(operational_data)

    return {
        key: sanitize(source.get(key), key=key)
        for key in UDYAM_MONITORED_KEYS
    }


def capture_work_snapshot(
    *,
    work_item: Any,
    process_step_code: str | None = None,
    process_step_id: Any = None,
    current_controller: str | None = None,
    next_action: str | None = None,
) -> dict[str, Any]:
    """Capture only diagnostic fields with known dependency value."""

    return {
        "work": {
            "id": _as_text(
                getattr(work_item, "id", "")
            ),
            "tenant_id": _as_text(
                getattr(work_item, "tenant_id", "")
            ),
            "service_id": _as_text(
                getattr(work_item, "service_id", "")
            ),
            "status": _as_text(
                getattr(work_item, "status", "")
            ),
            "owner_user_id": _as_text(
                getattr(work_item, "owner_user_id", "")
            ),
            "reviewer_user_id": _as_text(
                getattr(work_item, "reviewer_user_id", "")
            ),
            "row_version": getattr(
                work_item,
                "row_version",
                None,
            ),
            "updated_at": _as_text(
                getattr(work_item, "updated_at", "")
            ),
        },
        "process": {
            "step_id": _as_text(process_step_id),
            "step_code": _as_text(process_step_code),
        },
        "udyam": monitored_udyam_data(
            getattr(
                work_item,
                "operational_data",
                None,
            )
        ),
        "control": {
            "current_controller": _as_text(
                current_controller
            ),
            "next_action": _as_text(
                next_action
            ),
        },
    }


# ---------------------------------------------------------------------
# Diff
# ---------------------------------------------------------------------

def _flatten(
    value: Any,
    prefix: str = "",
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {prefix: value}

    result: dict[str, Any] = {}

    for key, child in value.items():
        path = (
            f"{prefix}.{key}"
            if prefix
            else str(key)
        )

        if isinstance(child, Mapping):
            result.update(
                _flatten(
                    child,
                    path,
                )
            )
        else:
            result[path] = child

    return result


def diff_snapshots(
    before: Mapping[str, Any],
    after: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    """Return only values that actually changed."""

    old = _flatten(before)
    new = _flatten(after)

    result = {}

    for key in sorted(set(old) | set(new)):
        previous = old.get(key)
        current = new.get(key)

        if previous != current:
            result[key] = {
                "before": previous,
                "after": current,
            }

    return result


# ---------------------------------------------------------------------
# Dependency evaluation
# ---------------------------------------------------------------------

def evaluate_dependency_contract(
    action: str,
    *,
    work_status: str,
    process_step_code: str | None,
) -> list[dict[str, Any]]:
    contract = UDYAM_ACTION_CONTRACTS.get(action)

    if contract is None:
        return [
            {
                "dependency": "action_contract",
                "passed": False,
                "expected": "configured dependency contract",
                "actual": action,
            }
        ]

    checks = []

    if contract.allowed_work_statuses:
        checks.append(
            {
                "dependency": "work.status",
                "passed": (
                    work_status
                    in contract.allowed_work_statuses
                ),
                "expected": list(
                    contract.allowed_work_statuses
                ),
                "actual": work_status,
            }
        )

    if contract.required_process_step:
        checks.append(
            {
                "dependency": "process.current_step",
                "passed": (
                    process_step_code
                    == contract.required_process_step
                ),
                "expected": (
                    contract.required_process_step
                ),
                "actual": process_step_code or "",
            }
        )

    return checks


# ---------------------------------------------------------------------
# Udyam invariant engine
# ---------------------------------------------------------------------

def _present(value: Any) -> bool:
    if value is None:
        return False

    if isinstance(value, str):
        return bool(value.strip())

    return True


def evaluate_udyam_invariants(
    *,
    work_status: str,
    process_step_code: str | None,
    operational_data: Mapping[str, Any] | None,
) -> list[dict[str, Any]]:
    data = _clean_mapping(operational_data)

    step = str(process_step_code or "")

    results: list[dict[str, Any]] = []

    submission_required = step in {
        "APPLICATION_SUBMISSION",
        "QUERY_RESOLUTION",
        "COMPLETION",
    }

    if submission_required:
        for key in (
            "udyam_application_reference",
            "udyam_submission_date",
            "udyam_submission_time",
        ):
            results.append(
                {
                    "invariant": (
                        "UDYAM_SUBMISSION_IDENTITY_PRESENT"
                    ),
                    "field": key,
                    "passed": _present(data.get(key)),
                    "expected": "non-empty",
                    "actual": sanitize(
                        data.get(key),
                        key=key,
                    ),
                }
            )

    if step == "QUERY_RESOLUTION":
        for key in (
            "udyam_query_type",
            "udyam_query_remarks",
        ):
            results.append(
                {
                    "invariant": (
                        "UDYAM_QUERY_CONTEXT_PRESENT"
                    ),
                    "field": key,
                    "passed": _present(data.get(key)),
                    "expected": "non-empty",
                    "actual": sanitize(
                        data.get(key),
                        key=key,
                    ),
                }
            )

    if step == "COMPLETION":
        results.append(
            {
                "invariant": "UDYAM_CERTIFICATE_PRESENT",
                "field": "udyam_certificate_attachment_id",
                "passed": _present(
                    data.get(
                        "udyam_certificate_attachment_id"
                    )
                ),
                "expected": "non-empty",
                "actual": sanitize(
                    data.get(
                        "udyam_certificate_attachment_id"
                    ),
                    key="udyam_certificate_attachment_id",
                ),
            }
        )

        results.append(
            {
                "invariant": "WORK_COMPLETED",
                "field": "work.status",
                "passed": work_status == "COMPLETED",
                "expected": "COMPLETED",
                "actual": work_status,
            }
        )

    return results


def failed_invariants(
    results: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return [
        row
        for row in results
        if not row.get("passed")
    ]


# ---------------------------------------------------------------------
# Dependency impact
# ---------------------------------------------------------------------

def dependency_impact(
    changed_paths: Mapping[str, Any],
) -> list[str]:
    """Map changed state to the major downstream consumers.

    This is diagnostic guidance, not authorization logic.
    """

    dependents: set[str] = set()

    for path in changed_paths:

        if path.startswith("work.status"):
            dependents.update(
                {
                    "current_controller",
                    "can_edit",
                    "can_review",
                    "can_upload_internal",
                    "generic Save",
                    "review actions",
                    "Work grid",
                    "Work Health",
                }
            )

        if path.startswith("process."):
            dependents.update(
                {
                    "Udyam tracker",
                    "Udyam action availability",
                    "Udyam endpoint guards",
                    "effective_status",
                    "Work Health",
                }
            )

        if path.startswith(
            "udyam.udyam_application_reference"
        ) or path.startswith(
            "udyam.udyam_submission_date"
        ) or path.startswith(
            "udyam.udyam_submission_time"
        ):
            dependents.update(
                {
                    "Application Submitted panel",
                    "Query cycle",
                    "Completion evidence",
                    "History",
                    "Udyam state integrity",
                }
            )

        if path.startswith("udyam.udyam_query_"):
            dependents.update(
                {
                    "Query Resolution panel",
                    "Query history",
                    "Udyam state integrity",
                }
            )

        if path.startswith(
            "udyam.udyam_certificate_attachment_id"
        ):
            dependents.update(
                {
                    "Certificate download",
                    "Completion history",
                    "Udyam terminal state",
                }
            )

    return sorted(dependents)


def diagnostic_event_payload(
    *,
    action: str,
    result: str,
    before: Mapping[str, Any],
    after: Mapping[str, Any],
    work_status: str,
    process_step_code: str | None,
    correlation_id: str = "",
    failure_code: str = "",
    failure_detail: str = "",
) -> dict[str, Any]:
    """Build the canonical metadata body later stored in AuditEvent."""

    changes = diff_snapshots(
        before,
        after,
    )

    dependencies = evaluate_dependency_contract(
        action,
        work_status=work_status,
        process_step_code=process_step_code,
    )

    invariants = evaluate_udyam_invariants(
        work_status=work_status,
        process_step_code=process_step_code,
        operational_data=(
            after.get("udyam", {})
            if isinstance(after, Mapping)
            else {}
        ),
    )

    contract = UDYAM_ACTION_CONTRACTS.get(action)

    return sanitize(
        {
            "observability_version": 1,
            "action": action,
            "result": result,
            "correlation_id": correlation_id,
            "dependencies": dependencies,
            "reads": (
                list(contract.reads)
                if contract
                else []
            ),
            "writes": (
                list(contract.writes)
                if contract
                else []
            ),
            "changes": changes,
            "invariants": invariants,
            "invariant_failures": failed_invariants(
                invariants
            ),
            "downstream_dependents": (
                sorted(
                    set(
                        dependency_impact(changes)
                    )
                    | set(
                        contract.downstream_dependents
                        if contract
                        else ()
                    )
                )
            ),
            "failure": {
                "code": failure_code,
                "detail": failure_detail,
            }
            if failure_code or failure_detail
            else {},
        }
    )
