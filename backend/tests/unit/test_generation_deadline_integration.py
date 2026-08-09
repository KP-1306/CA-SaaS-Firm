from __future__ import annotations

import datetime as dt
from types import SimpleNamespace
from unittest.mock import patch

from contexts.generation.generation import (
    _resolved_values,
)


def _profile():
    return SimpleNamespace(
        tenant_id="11111111-1111-1111-1111-111111111111",
        service_id="33333333-3333-3333-3333-333333333333",
        subscription_id="44444444-4444-4444-4444-444444444444",
        task_template_id="55555555-5555-5555-5555-555555555555",
        frequency="MONTHLY",
        default_owner_user_id=None,
        default_reviewer_user_id=None,
    )


def _template(default_due_days=10):
    return SimpleNamespace(
        name="Monthly compliance",
        description="",
        default_title="",
        default_priority="NORMAL",
        default_owner_user_id=None,
        default_reviewer_user_id=None,
        default_due_days=default_due_days,
        default_estimated_hours=None,
    )


def _subscription():
    return SimpleNamespace(
        default_owner_user_id=None,
        default_reviewer_user_id=None,
    )


@patch(
    "contexts.generation.generation."
    "_subscription_for"
)
@patch(
    "contexts.generation.generation."
    "_template_for"
)
@patch(
    "contexts.generation.generation."
    "calculate_compliance_due_date"
)
def test_statutory_deadline_has_precedence(
    calculate,
    template_for,
    subscription_for,
):
    calculate.return_value = dt.date(2026, 8, 20)
    template_for.return_value = _template(
        default_due_days=10,
    )
    subscription_for.return_value = _subscription()

    resolved = _resolved_values(
        _profile(),
        on_date=dt.date(2026, 7, 5),
    )

    assert resolved["due_date"] == dt.date(
        2026,
        8,
        20,
    )

    calculate.assert_called_once_with(
        tenant_id=(
            "11111111-1111-1111-1111-111111111111"
        ),
        service_id=(
            "33333333-3333-3333-3333-333333333333"
        ),
        frequency="MONTHLY",
        on_date=dt.date(2026, 7, 5),
    )


@patch(
    "contexts.generation.generation."
    "_subscription_for"
)
@patch(
    "contexts.generation.generation."
    "_template_for"
)
@patch(
    "contexts.generation.generation."
    "calculate_compliance_due_date"
)
def test_template_offset_remains_fallback(
    calculate,
    template_for,
    subscription_for,
):
    calculate.return_value = None
    template_for.return_value = _template(
        default_due_days=10,
    )
    subscription_for.return_value = _subscription()

    resolved = _resolved_values(
        _profile(),
        on_date=dt.date(2026, 7, 5),
    )

    assert resolved["due_date"] == dt.date(
        2026,
        7,
        15,
    )


@patch(
    "contexts.generation.generation."
    "_subscription_for"
)
@patch(
    "contexts.generation.generation."
    "_template_for"
)
@patch(
    "contexts.generation.generation."
    "calculate_compliance_due_date"
)
def test_no_rule_and_no_template_offset_keeps_none(
    calculate,
    template_for,
    subscription_for,
):
    calculate.return_value = None
    template_for.return_value = _template(
        default_due_days=None,
    )
    subscription_for.return_value = _subscription()

    resolved = _resolved_values(
        _profile(),
        on_date=dt.date(2026, 7, 5),
    )

    assert resolved["due_date"] is None
