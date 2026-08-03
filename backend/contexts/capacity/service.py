"""Deterministic capacity calculation service (Employee Operations V1).

All functions are pure over tenant-scoped rows and return plain values/dicts.
Hours are the base unit; percentages and aggregates are derived here and never
stored. Every function is safe on empty data and independent of wall-clock time
except where a date range is passed in explicitly.

Nothing here mutates state; the service is read-only aggregation used by the
assignment engine and the insight dashboards.
"""

from __future__ import annotations

import datetime as _dt
from decimal import Decimal

from .models import (
    CapacityOverride,
    CapacityProfile,
    CapacityReservation,
    Holiday,
    LeaveRecord,
    LeaveStatus,
)

_WEEKDAY_FIELDS = (
    "works_monday",
    "works_tuesday",
    "works_wednesday",
    "works_thursday",
    "works_friday",
    "works_saturday",
    "works_sunday",
)


def _active_profile(tenant_id, employee_id, on_date):
    """Return the effective CapacityProfile for an employee on a date, or None."""
    qs = CapacityProfile.objects.filter(
        tenant_id=tenant_id, employee_id=employee_id, is_active=True
    )
    best = None
    for p in qs:
        if p.effective_from and p.effective_from > on_date:
            continue
        if p.effective_to and p.effective_to < on_date:
            continue
        # Prefer the most recent effective_from that still applies.
        if best is None or (p.effective_from or _dt.date.min) >= (best.effective_from or _dt.date.min):
            best = p
    return best


def _is_working_day(profile, on_date) -> bool:
    if profile is None:
        # Default working pattern Mon-Fri when no profile exists.
        return on_date.weekday() < 5
    field = _WEEKDAY_FIELDS[on_date.weekday()]
    return bool(getattr(profile, field))


def is_holiday(tenant_id, on_date, *, branch_id=None, team_id=None) -> bool:
    """True when the date is a non-working holiday in the resolved scope."""
    qs = Holiday.objects.filter(tenant_id=tenant_id, holiday_date=on_date, is_active=True)
    for h in qs:
        # Tenant-wide holiday applies to everyone.
        if h.branch_id is None and h.team_id is None:
            return True
        if branch_id is not None and h.branch_id == branch_id:
            return True
        if team_id is not None and h.team_id == team_id:
            return True
    return False


def _approved_leave_hours(tenant_id, employee_id, on_date, base_daily) -> Decimal:
    """Hours removed by approved leave on a date (full or partial day)."""
    total = Decimal("0")
    qs = LeaveRecord.objects.filter(
        tenant_id=tenant_id,
        employee_id=employee_id,
        status=LeaveStatus.APPROVED,
        start_date__lte=on_date,
        end_date__gte=on_date,
    )
    for lv in qs:
        if lv.is_partial_day and lv.hours is not None:
            total += Decimal(lv.hours)
        else:
            total += Decimal(base_daily)
    return total


def _override_delta(tenant_id, employee_id, on_date) -> Decimal:
    total = Decimal("0")
    for o in CapacityOverride.objects.filter(
        tenant_id=tenant_id, employee_id=employee_id, override_date=on_date, is_active=True
    ):
        total += Decimal(o.delta_hours)
    return total


def available_hours_on(tenant_id, employee_id, on_date, *, branch_id=None, team_id=None) -> Decimal:
    """Derived available hours for an employee on a single date.

    base (profile daily hours if a working day) - approved leave + net override,
    zeroed on holidays/non-working days, never negative.
    """
    profile = _active_profile(tenant_id, employee_id, on_date)
    if not _is_working_day(profile, on_date):
        return Decimal("0")
    if is_holiday(tenant_id, on_date, branch_id=branch_id, team_id=team_id):
        return Decimal("0")
    base_daily = Decimal(profile.daily_hours) if profile else Decimal("8")
    leave = _approved_leave_hours(tenant_id, employee_id, on_date, base_daily)
    delta = _override_delta(tenant_id, employee_id, on_date)
    available = base_daily - leave + delta
    return available if available > 0 else Decimal("0")


def available_hours_range(tenant_id, employee_id, start_date, end_date, *, branch_id=None, team_id=None) -> Decimal:
    """Sum of derived available hours across an inclusive date range."""
    if end_date < start_date:
        return Decimal("0")
    total = Decimal("0")
    day = start_date
    while day <= end_date:
        total += available_hours_on(
            tenant_id, employee_id, day, branch_id=branch_id, team_id=team_id
        )
        day += _dt.timedelta(days=1)
    return total


def reserved_hours_range(tenant_id, employee_id, start_date, end_date) -> Decimal:
    """Sum of active reservation hours overlapping a range."""
    total = Decimal("0")
    for r in CapacityReservation.objects.filter(
        tenant_id=tenant_id, employee_id=employee_id, is_active=True
    ):
        r_end = r.end_date or r.start_date
        if r.start_date <= end_date and r_end >= start_date:
            total += Decimal(r.hours)
    return total


def utilization(allocated_hours, available_hours) -> float:
    """Derived utilization percentage (0..>100). Safe on zero availability."""
    a = Decimal(available_hours or 0)
    if a <= 0:
        return 0.0
    return float((Decimal(allocated_hours or 0) / a) * 100)


def capacity_summary(tenant_id, employee_id, start_date, end_date, *, allocated_hours=0, branch_id=None, team_id=None) -> dict:
    """Deterministic capacity snapshot for a range (all derived)."""
    available = available_hours_range(
        tenant_id, employee_id, start_date, end_date, branch_id=branch_id, team_id=team_id
    )
    reserved = reserved_hours_range(tenant_id, employee_id, start_date, end_date)
    allocated = Decimal(allocated_hours or 0) + reserved
    remaining = available - allocated
    return {
        "employee_id": str(employee_id),
        "period_start": start_date.isoformat(),
        "period_end": end_date.isoformat(),
        "available_hours": float(available),
        "allocated_hours": float(allocated),
        "reserved_hours": float(reserved),
        "remaining_hours": float(remaining),
        "utilization_percent": utilization(allocated, available),
        "over_allocated": remaining < 0,
    }
