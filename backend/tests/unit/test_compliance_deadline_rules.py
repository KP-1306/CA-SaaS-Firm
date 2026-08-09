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


def _rule(**kwargs):
    values = {
        "tenant_id": TENANT,
        "service_id": SERVICE,
        "frequency": "MONTHLY",
        "due_day": 20,
        "due_month_offset": 1,
        "created_by": TENANT,
        "updated_by": TENANT,
    }
    values.update(kwargs)

    return ComplianceDeadlineRule.objects.create(
        **values
    )


@pytest.mark.django_db
def test_monthly_following_month_due_date():
    _rule()

    result = calculate_compliance_due_date(
        tenant_id=TENANT,
        service_id=SERVICE,
        frequency="MONTHLY",
        on_date=dt.date(2026, 7, 5),
    )

    assert result == dt.date(2026, 8, 20)


@pytest.mark.django_db
def test_quarterly_due_date_uses_quarter_end():
    _rule(
        frequency="QUARTERLY",
        due_day=15,
        due_month_offset=1,
    )

    result = calculate_compliance_due_date(
        tenant_id=TENANT,
        service_id=SERVICE,
        frequency="QUARTERLY",
        on_date=dt.date(2026, 8, 10),
    )

    assert result == dt.date(2026, 10, 15)


@pytest.mark.django_db
def test_half_yearly_due_date_uses_half_end():
    _rule(
        frequency="HALF_YEARLY",
        due_day=31,
        due_month_offset=1,
    )

    result = calculate_compliance_due_date(
        tenant_id=TENANT,
        service_id=SERVICE,
        frequency="HALF_YEARLY",
        on_date=dt.date(2026, 4, 10),
    )

    assert result == dt.date(2026, 7, 31)


@pytest.mark.django_db
def test_yearly_due_date_rolls_into_next_year():
    _rule(
        frequency="YEARLY",
        due_day=31,
        due_month_offset=1,
    )

    result = calculate_compliance_due_date(
        tenant_id=TENANT,
        service_id=SERVICE,
        frequency="YEARLY",
        on_date=dt.date(2026, 8, 10),
    )

    assert result == dt.date(2027, 1, 31)


@pytest.mark.django_db
def test_no_applicable_rule_returns_none():
    result = calculate_compliance_due_date(
        tenant_id=TENANT,
        service_id=SERVICE,
        frequency="MONTHLY",
        on_date=dt.date(2026, 7, 5),
    )

    assert result is None


@pytest.mark.django_db
def test_effective_dates_select_correct_rule():
    _rule(
        due_day=10,
        effective_until=dt.date(2026, 6, 30),
    )

    _rule(
        due_day=20,
        effective_from=dt.date(2026, 7, 1),
    )

    result = calculate_compliance_due_date(
        tenant_id=TENANT,
        service_id=SERVICE,
        frequency="MONTHLY",
        on_date=dt.date(2026, 7, 5),
    )

    assert result == dt.date(2026, 8, 20)


@pytest.mark.django_db
def test_invalid_due_day_fails_closed():
    _rule(
        due_day=31,
        due_month_offset=1,
    )

    with pytest.raises(
        ValueError,
        match="invalid",
    ):
        calculate_compliance_due_date(
            tenant_id=TENANT,
            service_id=SERVICE,
            frequency="MONTHLY",
            on_date=dt.date(2026, 1, 5),
        )



@pytest.mark.django_db
def test_quarter_specific_rule_overrides_generic_rule():
    # Generic Apr-Mar financial-year quarterly rule.
    _rule(
        frequency="QUARTERLY",
        due_day=25,
        due_month_offset=1,
        period_number=None,
        period_start_month=4,
    )

    # Q4 (Jan-Mar) has a different statutory pattern.
    _rule(
        frequency="QUARTERLY",
        due_day=31,
        due_month_offset=2,
        period_number=4,
        period_start_month=4,
    )

    result = calculate_compliance_due_date(
        tenant_id=TENANT,
        service_id=SERVICE,
        frequency="QUARTERLY",
        on_date=dt.date(2027, 2, 15),
    )

    # Jan-Mar ends in March; +2 months => May.
    assert result == dt.date(2027, 5, 31)

@pytest.mark.django_db
def test_generic_rule_remains_fallback_when_no_specific_rule():
    _rule(
        frequency="QUARTERLY",
        due_day=15,
        due_month_offset=1,
        period_number=None,
    )

    _rule(
        frequency="QUARTERLY",
        due_day=31,
        due_month_offset=2,
        period_number=4,
    )

    result = calculate_compliance_due_date(
        tenant_id=TENANT,
        service_id=SERVICE,
        frequency="QUARTERLY",
        on_date=dt.date(2026, 5, 15),
    )

    assert result == dt.date(2026, 7, 15)


@pytest.mark.django_db
def test_quarter_one_specific_rule():
    _rule(
        frequency="QUARTERLY",
        due_day=31,
        due_month_offset=1,
        period_number=1,
        period_start_month=4,
    )

    result = calculate_compliance_due_date(
        tenant_id=TENANT,
        service_id=SERVICE,
        frequency="QUARTERLY",
        on_date=dt.date(2026, 5, 10),
    )

    # Apr-Jun is fiscal Q1; +1 month => July.
    assert result == dt.date(2026, 7, 31)

@pytest.mark.django_db
def test_quarter_four_can_use_different_month_offset():
    _rule(
        frequency="QUARTERLY",
        due_day=31,
        due_month_offset=2,
        period_number=4,
        period_start_month=4,
    )

    result = calculate_compliance_due_date(
        tenant_id=TENANT,
        service_id=SERVICE,
        frequency="QUARTERLY",
        on_date=dt.date(2027, 2, 10),
    )

    # Jan-Mar is fiscal Q4; +2 months => May.
    assert result == dt.date(2027, 5, 31)

@pytest.mark.django_db
def test_month_specific_rule_uses_calendar_month_number():
    _rule(
        frequency="MONTHLY",
        due_day=10,
        due_month_offset=1,
        period_number=None,
    )

    _rule(
        frequency="MONTHLY",
        due_day=20,
        due_month_offset=1,
        period_number=7,
    )

    result = calculate_compliance_due_date(
        tenant_id=TENANT,
        service_id=SERVICE,
        frequency="MONTHLY",
        on_date=dt.date(2026, 7, 5),
    )

    assert result == dt.date(2026, 8, 20)



@pytest.mark.django_db
def test_fiscal_quarter_cycle_positions():
    from contexts.configuration.deadline_rules import (
        _period_number_for,
    )

    assert _period_number_for(
        "QUARTERLY",
        dt.date(2026, 4, 1),
        period_start_month=4,
    ) == 1

    assert _period_number_for(
        "QUARTERLY",
        dt.date(2026, 7, 1),
        period_start_month=4,
    ) == 2

    assert _period_number_for(
        "QUARTERLY",
        dt.date(2026, 10, 1),
        period_start_month=4,
    ) == 3

    assert _period_number_for(
        "QUARTERLY",
        dt.date(2027, 1, 1),
        period_start_month=4,
    ) == 4


@pytest.mark.django_db
def test_calendar_cycle_remains_backward_compatible():
    from contexts.configuration.deadline_rules import (
        _period_number_for,
    )

    assert _period_number_for(
        "QUARTERLY",
        dt.date(2026, 2, 1),
        period_start_month=1,
    ) == 1

    assert _period_number_for(
        "QUARTERLY",
        dt.date(2026, 11, 1),
        period_start_month=1,
    ) == 4
