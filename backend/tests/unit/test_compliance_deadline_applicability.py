from __future__ import annotations

import datetime as dt
import uuid

import pytest

from contexts.configuration.deadline_rules import (
    calculate_compliance_due_date,
)
from contexts.configuration.models import (
    ComplianceDeadlineRule,
)


TENANT = uuid.UUID(
    "11111111-1111-1111-1111-111111111111"
)

SERVICE = uuid.UUID(
    "33333333-3333-3333-3333-333333333333"
)

PRINCIPAL = uuid.UUID(
    "22222222-2222-2222-2222-222222222222"
)


def _rule(**kwargs):
    values = {
        "tenant_id": TENANT,
        "service_id": SERVICE,
        "frequency": "QUARTERLY",
        "period_start_month": 4,
        "period_number": None,
        "due_day": 25,
        "due_month_offset": 1,
        "applicability": {},
        "created_by": PRINCIPAL,
        "updated_by": PRINCIPAL,
    }

    values.update(kwargs)

    return ComplianceDeadlineRule.objects.create(
        **values
    )


@pytest.mark.django_db
def test_unconditional_rule_matches_without_context():
    _rule(
        due_day=20,
    )

    result = calculate_compliance_due_date(
        tenant_id=TENANT,
        service_id=SERVICE,
        frequency="QUARTERLY",
        on_date=dt.date(2026, 8, 10),
    )

    assert result == dt.date(2026, 10, 20)


@pytest.mark.django_db
def test_conditional_rule_requires_matching_context():
    _rule(
        due_day=31,
        applicability={
            "tds_form": "26Q",
        },
    )

    result = calculate_compliance_due_date(
        tenant_id=TENANT,
        service_id=SERVICE,
        frequency="QUARTERLY",
        on_date=dt.date(2026, 8, 10),
        operational_context={
            "tds_form": "24Q",
        },
    )

    assert result is None


@pytest.mark.django_db
def test_conditional_rule_matches_exact_value():
    _rule(
        due_day=31,
        applicability={
            "tds_form": "26Q",
        },
    )

    result = calculate_compliance_due_date(
        tenant_id=TENANT,
        service_id=SERVICE,
        frequency="QUARTERLY",
        on_date=dt.date(2026, 8, 10),
        operational_context={
            "tds_form": "26Q",
        },
    )

    assert result == dt.date(2026, 10, 31)


@pytest.mark.django_db
def test_missing_context_does_not_match_conditional_rule():
    _rule(
        applicability={
            "tds_form": "26Q",
        },
    )

    result = calculate_compliance_due_date(
        tenant_id=TENANT,
        service_id=SERVICE,
        frequency="QUARTERLY",
        on_date=dt.date(2026, 8, 10),
        operational_context={},
    )

    assert result is None


@pytest.mark.django_db
def test_all_applicability_keys_must_match():
    _rule(
        due_day=31,
        applicability={
            "tds_form": "26Q",
            "entity_type": "COMPANY",
        },
    )

    result = calculate_compliance_due_date(
        tenant_id=TENANT,
        service_id=SERVICE,
        frequency="QUARTERLY",
        on_date=dt.date(2026, 8, 10),
        operational_context={
            "tds_form": "26Q",
            "entity_type": "INDIVIDUAL",
        },
    )

    assert result is None


@pytest.mark.django_db
def test_conditional_rule_beats_unconditional_rule():
    _rule(
        due_day=20,
        applicability={},
    )

    _rule(
        due_day=31,
        applicability={
            "tds_form": "26Q",
        },
    )

    result = calculate_compliance_due_date(
        tenant_id=TENANT,
        service_id=SERVICE,
        frequency="QUARTERLY",
        on_date=dt.date(2026, 8, 10),
        operational_context={
            "tds_form": "26Q",
        },
    )

    assert result == dt.date(2026, 10, 31)


@pytest.mark.django_db
def test_period_specific_conditional_rule_has_highest_priority():
    _rule(
        due_day=20,
        applicability={},
    )

    _rule(
        due_day=25,
        applicability={
            "tds_form": "26Q",
        },
    )

    _rule(
        period_number=2,
        due_day=31,
        applicability={
            "tds_form": "26Q",
        },
    )

    result = calculate_compliance_due_date(
        tenant_id=TENANT,
        service_id=SERVICE,
        frequency="QUARTERLY",
        on_date=dt.date(2026, 8, 10),
        operational_context={
            "tds_form": "26Q",
        },
    )

    assert result == dt.date(2026, 10, 31)


@pytest.mark.django_db
def test_more_specific_applicability_wins():
    _rule(
        due_day=20,
        applicability={
            "tds_form": "26Q",
        },
    )

    _rule(
        due_day=31,
        applicability={
            "tds_form": "26Q",
            "entity_type": "COMPANY",
        },
    )

    result = calculate_compliance_due_date(
        tenant_id=TENANT,
        service_id=SERVICE,
        frequency="QUARTERLY",
        on_date=dt.date(2026, 8, 10),
        operational_context={
            "tds_form": "26Q",
            "entity_type": "COMPANY",
        },
    )

    assert result == dt.date(2026, 10, 31)


@pytest.mark.django_db
def test_invalid_applicability_shape_fails_closed():
    _rule(
        applicability=[
            "tds_form",
            "26Q",
        ],
    )

    with pytest.raises(
        ValueError,
        match="applicability must be an object",
    ):
        calculate_compliance_due_date(
            tenant_id=TENANT,
            service_id=SERVICE,
            frequency="QUARTERLY",
            on_date=dt.date(2026, 8, 10),
            operational_context={
                "tds_form": "26Q",
            },
        )
