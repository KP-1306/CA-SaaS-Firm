from __future__ import annotations

from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch
import uuid

import pytest
from django.utils import timezone

from contexts.work.work_health import (
    _current_controller,
    _due_health,
    _progress,
    _value_present,
    calculate_work_health,
)


def _work(**overrides):
    now = timezone.now()

    values = {
        "id": uuid.uuid4(),
        "tenant_id": uuid.uuid4(),
        "service_id": None,
        "operational_data": {},
        "due_date": None,
        "status": "IN_PROGRESS",
        "priority": "NORMAL",
        "submitted_for_review_at": None,
        "created_at": now,
        "updated_at": now,
    }

    values.update(overrides)

    return SimpleNamespace(**values)


def test_operational_value_presence_handles_false_and_zero():
    assert _value_present(False) is True
    assert _value_present(0) is True
    assert _value_present("") is False
    assert _value_present("   ") is False
    assert _value_present(None) is False
    assert _value_present([]) is False
    assert _value_present(["x"]) is True


def test_due_state_distinguishes_due_soon_and_overdue():
    today = timezone.now().date()

    due_soon = _due_health(
        _work(
            due_date=today + timedelta(days=2),
        ),
        today,
    )

    overdue = _due_health(
        _work(
            due_date=today - timedelta(days=1),
        ),
        today,
    )

    assert due_soon["state"] == "DUE_SOON"
    assert due_soon["days_to_due"] == 2

    assert overdue["state"] == "OVERDUE"
    assert overdue["days_to_due"] == -1


@pytest.mark.parametrize(
    ("status", "controller"),
    (
        ("NOT_STARTED", "OWNER"),
        ("IN_PROGRESS", "OWNER"),
        ("REWORK_REQUIRED", "OWNER"),
        ("WAITING_FOR_CLIENT", "CLIENT"),
        ("READY_FOR_REVIEW", "REVIEWER"),
        ("COMPLETED", "NONE"),
        ("CANCELLED", "NONE"),
    ),
)
def test_controller_is_derived_from_certified_workflow(
    status,
    controller,
):
    assert _current_controller(
        _work(status=status)
    ) == controller


def test_progress_uses_only_configured_dimensions():
    work = _work(status="IN_PROGRESS")

    progress = _progress(
        work,
        {
            "total": 4,
            "completion_percent": 50,
        },
        {
            "total": 2,
            "satisfied": 1,
        },
    )

    # Fields: 40*50, docs: 30*50, review/completion: 0.
    # 3500 / 100 = 35.
    assert progress == 35


@patch(
    "contexts.work.work_health."
    "_operational_health"
)
@patch(
    "contexts.work.work_health."
    "_document_health"
)
@patch(
    "contexts.work.work_health."
    "_waiting_health"
)
def test_health_snapshot_contract(
    waiting,
    documents,
    operational,
):
    now = timezone.now()

    operational.return_value = {
        "total": 4,
        "completed": 3,
        "remaining": 1,
        "mandatory_total": 2,
        "mandatory_completed": 1,
        "mandatory_remaining": 1,
        "completion_percent": 75,
    }

    documents.return_value = {
        "total": 5,
        "satisfied": 3,
        "pending": 2,
        "mandatory_total": 4,
        "mandatory_satisfied": 3,
        "mandatory_missing": 1,
        "missing": 1,
        "pending_review": 1,
        "rejected": 0,
        "expired": 0,
        "pending_acceptance": 1,
        "ready_for_review": False,
        "readiness_state": "WAITING_FOR_CLIENT",
        "health_score": 60,
        "blockers": [],
    }

    waiting.return_value = {
        "waiting_days": 6,
        "waiting_since": (
            now - timedelta(days=6)
        ).isoformat(),
    }

    snapshot = calculate_work_health(
        _work(
            status="WAITING_FOR_CLIENT",
            due_date=(
                now.date() + timedelta(days=2)
            ),
        ),
        now=now,
    )

    assert snapshot["contract_version"] == 1
    assert snapshot["health"] == "AMBER"
    assert snapshot["risk"] == "MEDIUM"
    assert snapshot["current_controller"] == "CLIENT"
    assert snapshot["waiting_days"] == 6
    assert snapshot["due_state"] == "DUE_SOON"

    assert (
        snapshot["operational"]["mandatory_remaining"]
        == 1
    )

    assert snapshot["documents"]["missing"] == 1

    assert snapshot["next_action"] == {
        "code": "AWAIT_CLIENT_DOCUMENTS",
        "label": "Await client documents",
    }


@patch(
    "contexts.work.work_health."
    "_operational_health"
)
@patch(
    "contexts.work.work_health."
    "_document_health"
)
@patch(
    "contexts.work.work_health."
    "_waiting_health"
)
def test_overdue_work_is_high_risk_red(
    waiting,
    documents,
    operational,
):
    now = timezone.now()

    operational.return_value = {
        "total": 0,
        "completed": 0,
        "remaining": 0,
        "mandatory_total": 0,
        "mandatory_completed": 0,
        "mandatory_remaining": 0,
        "completion_percent": None,
    }

    documents.return_value = {
        "total": 0,
        "satisfied": 0,
        "pending": 0,
        "mandatory_total": 0,
        "mandatory_satisfied": 0,
        "mandatory_missing": 0,
        "missing": 0,
        "pending_review": 0,
        "rejected": 0,
        "expired": 0,
        "pending_acceptance": 0,
        "ready_for_review": True,
        "readiness_state": "READY",
        "health_score": 100,
        "blockers": [],
    }

    waiting.return_value = {
        "waiting_days": 1,
        "waiting_since": now.isoformat(),
    }

    snapshot = calculate_work_health(
        _work(
            due_date=(
                now.date() - timedelta(days=1)
            ),
        ),
        now=now,
    )

    assert snapshot["risk"] == "HIGH"
    assert snapshot["health"] == "RED"
    assert "Work is overdue." in snapshot["reasons"]


@patch(
    "contexts.work.work_health."
    "_operational_health"
)
@patch(
    "contexts.work.work_health."
    "_document_health"
)
@patch(
    "contexts.work.work_health."
    "_waiting_health"
)
def test_completed_work_is_green_and_complete(
    waiting,
    documents,
    operational,
):
    now = timezone.now()

    operational.return_value = {
        "total": 2,
        "completed": 2,
        "remaining": 0,
        "mandatory_total": 2,
        "mandatory_completed": 2,
        "mandatory_remaining": 0,
        "completion_percent": 100,
    }

    documents.return_value = {
        "total": 2,
        "satisfied": 2,
        "pending": 0,
        "mandatory_total": 2,
        "mandatory_satisfied": 2,
        "mandatory_missing": 0,
        "missing": 0,
        "pending_review": 0,
        "rejected": 0,
        "expired": 0,
        "pending_acceptance": 0,
        "ready_for_review": True,
        "readiness_state": "READY",
        "health_score": 100,
        "blockers": [],
    }

    waiting.return_value = {
        "waiting_days": 0,
        "waiting_since": None,
    }

    snapshot = calculate_work_health(
        _work(status="COMPLETED"),
        now=now,
    )

    assert snapshot["progress"] == 100
    assert snapshot["health"] == "GREEN"
    assert snapshot["risk"] == "LOW"
    assert snapshot["current_controller"] == "NONE"
    assert snapshot["next_action"]["code"] == "NONE"
