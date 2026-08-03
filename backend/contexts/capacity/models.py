"""Capacity, availability, leave and holiday models (Employee Operations V1).

Design principles (approved decisions 2, 6, 8, 9):

* **Hours are the stored base unit.** Utilization percentages, monthly capacity
  and remaining capacity are DERIVED by the service layer, never stored, so no
  redundant mutable total can drift.
* **Effective-dated.** CapacityProfile carries ``effective_from``/``effective_to``
  so working patterns change over time without rewriting history.
* **Additive & tenant-scoped.** Every model derives from ``TenantModel`` and uses
  UUID cross-references (never ForeignKey).

Nothing here performs payroll, attendance-device integration or statutory leave
accounting.
"""

from __future__ import annotations

from django.db import models

from core.db.models import TenantModel


class CapacityProfile(TenantModel):
    """An employee's effective-dated working pattern.

    Daily hours plus a weekly working-day pattern (Mon..Sun booleans) define
    baseline availability. Weekly capacity is derived (sum of working days x
    daily hours); it is not stored. At most one active profile per employee for
    a given period is expected; overlapping windows are validated in the
    serializer rather than by a DB constraint (ranges are not uniquely
    constrainable portably).
    """

    employee_id = models.UUIDField(db_index=True)
    daily_hours = models.DecimalField(max_digits=5, decimal_places=2, default=8)
    works_monday = models.BooleanField(default=True)
    works_tuesday = models.BooleanField(default=True)
    works_wednesday = models.BooleanField(default=True)
    works_thursday = models.BooleanField(default=True)
    works_friday = models.BooleanField(default=True)
    works_saturday = models.BooleanField(default=False)
    works_sunday = models.BooleanField(default=False)
    effective_from = models.DateField(null=True, blank=True)
    effective_to = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-effective_from", "-created_at"]
        indexes = [models.Index(
                fields=["tenant_id", "employee_id", "is_active"],
                name="ix_capprofile_emp_active",
            )]


class CapacityOverride(TenantModel):
    """A dated adjustment to an employee's available hours.

    Positive or negative delta hours applied on a specific date (e.g. a
    half-day training reducing capacity). Derived availability subtracts the net
    override for the day.
    """

    employee_id = models.UUIDField(db_index=True)
    override_date = models.DateField(db_index=True)
    delta_hours = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    reason = models.CharField(max_length=200, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-override_date"]


class CapacityReservation(TenantModel):
    """A future reservation of hours against an employee (soft allocation).

    Used to hold capacity for planned work before a WorkItem exists or before
    formal assignment. ``hours`` reserved across ``[start_date, end_date]``.
    """

    employee_id = models.UUIDField(db_index=True)
    start_date = models.DateField(db_index=True)
    end_date = models.DateField(null=True, blank=True)
    hours = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    work_item_id = models.UUIDField(null=True, blank=True, db_index=True)
    reason = models.CharField(max_length=200, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-start_date"]


class LeaveType(TenantModel):
    """A firm-configurable leave type (e.g. Casual, Sick, Earned).

    ``is_paid`` is descriptive only (no payroll in V1). Tenant-scoped unique
    ``code``.
    """

    name = models.CharField(max_length=120)
    code = models.CharField(max_length=30)
    is_paid = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["tenant_id", "code"], name="uq_leave_type_code_tenant")]
        ordering = ["name"]


class LeaveStatus(models.TextChoices):
    REQUESTED = "REQUESTED", "Requested"
    APPROVED = "APPROVED", "Approved"
    REJECTED = "REJECTED", "Rejected"
    CANCELLED = "CANCELLED", "Cancelled"


class LeaveRecord(TenantModel):
    """A minimal leave request/record (approved decision 8).

    Lifecycle: REQUESTED -> APPROVED | REJECTED, and REQUESTED/APPROVED ->
    CANCELLED. Partial-day leave is supported via ``is_partial_day`` +
    ``hours``. Overlap with existing non-terminal leave for the same employee is
    rejected in the serializer/service (clean 400, never a raw 500). Approved
    leave reduces derived availability.
    """

    employee_id = models.UUIDField(db_index=True)
    leave_type_id = models.UUIDField(null=True, blank=True, db_index=True)
    start_date = models.DateField(db_index=True)
    end_date = models.DateField(db_index=True)
    is_partial_day = models.BooleanField(default=False)
    hours = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    status = models.CharField(max_length=10, choices=LeaveStatus.choices, default=LeaveStatus.REQUESTED, db_index=True)
    reason = models.TextField(blank=True)
    approved_by = models.UUIDField(null=True, blank=True)
    decided_at = models.DateTimeField(null=True, blank=True)
    decision_comment = models.TextField(blank=True)

    class Meta:
        ordering = ["-start_date"]
        indexes = [models.Index(
                fields=["tenant_id", "employee_id", "status"],
                name="ix_leave_emp_status",
            )]


class Holiday(TenantModel):
    """A non-working day (approved decision 9).

    Scope resolves by precedence in the service layer: a tenant-wide holiday
    applies to everyone unless a branch/team scope narrows it. ``branch_id`` set
    => branch holiday; ``team_id`` set => team non-working day; both null =>
    tenant-wide.
    """

    name = models.CharField(max_length=160)
    holiday_date = models.DateField(db_index=True)
    branch_id = models.UUIDField(null=True, blank=True, db_index=True)
    team_id = models.UUIDField(null=True, blank=True, db_index=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["tenant_id", "holiday_date", "branch_id", "team_id"],
                name="uq_holiday_scope_date",
            )
        ]
        ordering = ["holiday_date"]
