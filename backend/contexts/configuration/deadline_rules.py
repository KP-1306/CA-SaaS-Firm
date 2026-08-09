from __future__ import annotations

import calendar
import datetime as dt

from .models import ComplianceDeadlineRule


def _validate_period_start_month(
    period_start_month: int,
) -> None:
    if period_start_month < 1 or period_start_month > 12:
        raise ValueError(
            "Compliance period_start_month must be between 1 and 12."
        )


def _cycle_start_year(
    on_date: dt.date,
    period_start_month: int,
) -> int:
    _validate_period_start_month(
        period_start_month,
    )

    if on_date.month >= period_start_month:
        return on_date.year

    return on_date.year - 1


def _relative_month_index(
    on_date: dt.date,
    period_start_month: int,
) -> int:
    _validate_period_start_month(
        period_start_month,
    )

    return (
        on_date.month
        - period_start_month
    ) % 12


def _period_number_for(
    frequency: str,
    on_date: dt.date,
    *,
    period_start_month: int = 1,
) -> int:
    relative_month = _relative_month_index(
        on_date,
        period_start_month,
    )

    if frequency == "MONTHLY":
        return relative_month + 1

    if frequency == "QUARTERLY":
        return (relative_month // 3) + 1

    if frequency == "HALF_YEARLY":
        return (relative_month // 6) + 1

    if frequency == "YEARLY":
        return 1

    raise ValueError(
        f"Unsupported compliance frequency: {frequency}"
    )


def _shift_month(
    year: int,
    month: int,
    offset: int,
) -> tuple[int, int]:
    absolute = (
        (year * 12)
        + (month - 1)
        + offset
    )

    return (
        absolute // 12,
        (absolute % 12) + 1,
    )


def _period_end_month(
    frequency: str,
    on_date: dt.date,
    *,
    period_start_month: int = 1,
) -> tuple[int, int]:
    period_number = _period_number_for(
        frequency,
        on_date,
        period_start_month=period_start_month,
    )

    cycle_year = _cycle_start_year(
        on_date,
        period_start_month,
    )

    if frequency == "MONTHLY":
        months_per_period = 1
    elif frequency == "QUARTERLY":
        months_per_period = 3
    elif frequency == "HALF_YEARLY":
        months_per_period = 6
    elif frequency == "YEARLY":
        months_per_period = 12
    else:
        raise ValueError(
            f"Unsupported compliance frequency: {frequency}"
        )

    # Offset from cycle start to the final month of the selected period.
    end_offset = (
        (period_number * months_per_period)
        - 1
    )

    return _shift_month(
        cycle_year,
        period_start_month,
        end_offset,
    )


def _effective_on(
    rule: ComplianceDeadlineRule,
    on_date: dt.date,
) -> bool:
    if (
        rule.effective_from
        and on_date < rule.effective_from
    ):
        return False

    if (
        rule.effective_until
        and on_date > rule.effective_until
    ):
        return False

    return True



def _applicability_matches(
    applicability,
    operational_context,
) -> bool:
    if applicability in (None, {}):
        return True

    if not isinstance(applicability, dict):
        raise ValueError(
            "Compliance deadline applicability must be an object."
        )

    context = operational_context or {}

    if not isinstance(context, dict):
        raise ValueError(
            "Compliance deadline operational context must be an object."
        )

    for key, expected in applicability.items():
        if not isinstance(key, str) or not key:
            raise ValueError(
                "Compliance deadline applicability keys must be "
                "non-empty strings."
            )

        if key not in context:
            return False

        if context[key] != expected:
            return False

    return True


def _select_rule(
    *,
    tenant_id,
    service_id,
    frequency: str,
    on_date: dt.date,
    operational_context: dict | None = None,
) -> ComplianceDeadlineRule | None:
    rules = ComplianceDeadlineRule.objects.filter(
        tenant_id=tenant_id,
        service_id=service_id,
        frequency=frequency,
        is_active=True,
    ).order_by(
        "-effective_from",
        "-created_at",
    )

    best_rule = None
    best_score = None

    for candidate in rules:
        if not _effective_on(
            candidate,
            on_date,
        ):
            continue

        applicability = candidate.applicability or {}

        if not _applicability_matches(
            applicability,
            operational_context,
        ):
            continue

        period_start_month = int(
            candidate.period_start_month
        )

        current_period = _period_number_for(
            frequency,
            on_date,
            period_start_month=period_start_month,
        )

        is_period_specific = (
            candidate.period_number is not None
        )

        if (
            is_period_specific
            and candidate.period_number != current_period
        ):
            continue

        # Higher score means a more specific applicable rule.
        #
        # 1. period-specific beats generic;
        # 2. conditional beats unconditional;
        # 3. among conditional rules, more keys beats fewer keys.
        #
        # Query ordering remains the tie-breaker because we retain
        # the first candidate encountered for an equal score.
        score = (
            1 if is_period_specific else 0,
            1 if applicability else 0,
            len(applicability),
        )

        if (
            best_score is None
            or score > best_score
        ):
            best_rule = candidate
            best_score = score

    return best_rule


def calculate_compliance_due_date(
    *,
    tenant_id,
    service_id,
    frequency: str,
    on_date: dt.date,
    operational_context: dict | None = None,
) -> dt.date | None:
    rule = _select_rule(
        tenant_id=tenant_id,
        service_id=service_id,
        frequency=frequency,
        on_date=on_date,
        operational_context=operational_context,
    )

    if rule is None:
        return None

    if rule.due_day < 1 or rule.due_day > 31:
        raise ValueError(
            "Compliance deadline due_day must be between 1 and 31."
        )

    period_start_month = int(
        rule.period_start_month
    )

    year, month = _period_end_month(
        frequency,
        on_date,
        period_start_month=period_start_month,
    )

    year, month = _shift_month(
        year,
        month,
        int(rule.due_month_offset),
    )

    last_day = calendar.monthrange(
        year,
        month,
    )[1]

    if rule.due_day > last_day:
        raise ValueError(
            f"Configured due_day {rule.due_day} is invalid "
            f"for {year:04d}-{month:02d}."
        )

    return dt.date(
        year,
        month,
        int(rule.due_day),
    )
