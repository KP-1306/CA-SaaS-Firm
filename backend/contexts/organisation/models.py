from __future__ import annotations

from django.db import models

from core.db.models import TenantModel


class ActiveStatus(models.TextChoices):
    ACTIVE = "ACTIVE", "Active"
    INACTIVE = "INACTIVE", "Inactive"


class FirmProfile(TenantModel):
    name = models.CharField(max_length=200)
    legal_name = models.CharField(max_length=250, blank=True)
    pan = models.CharField(max_length=10, blank=True)
    gstin = models.CharField(max_length=15, blank=True)
    email = models.EmailField(blank=True)
    mobile = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=ActiveStatus.choices, default=ActiveStatus.ACTIVE)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["tenant_id"], name="uq_firm_per_tenant")]


class Branch(TenantModel):
    name = models.CharField(max_length=160)
    code = models.CharField(max_length=30)
    address = models.TextField(blank=True)
    email = models.EmailField(blank=True)
    mobile = models.CharField(max_length=20, blank=True)
    status = models.CharField(max_length=10, choices=ActiveStatus.choices, default=ActiveStatus.ACTIVE)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["tenant_id", "code"], name="uq_branch_code_tenant")]
        ordering = ["name"]


class Team(TenantModel):
    name = models.CharField(max_length=160)
    code = models.CharField(max_length=30)
    branch_id = models.UUIDField(null=True, blank=True)
    lead_user_id = models.UUIDField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=ActiveStatus.choices, default=ActiveStatus.ACTIVE)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["tenant_id", "code"], name="uq_team_code_tenant")]
        ordering = ["name"]


# ---------------------------------------------------------------------------
# Employee Operations V1 — organisation extensions (additive)
#
# Department, Designation, TeamMembership and ReportingRelationship are new
# tenant-owned models. Every cross-reference is a UUID column (never a
# ForeignKey), consistent with the platform convention (integrity on
# ``(tenant_id, id)`` pairs). Nothing here alters FirmProfile, Branch or Team.
# ---------------------------------------------------------------------------


class Department(TenantModel):
    """A firm-configurable department (e.g. Direct Tax, Audit, Payroll).

    Tenant-scoped unique ``code``. ``head_user_id`` optionally references an
    Employee who heads the department. Purely organisational; grants no
    authority by itself.
    """

    name = models.CharField(max_length=160)
    code = models.CharField(max_length=30)
    description = models.TextField(blank=True)
    branch_id = models.UUIDField(null=True, blank=True, db_index=True)
    head_user_id = models.UUIDField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=ActiveStatus.choices, default=ActiveStatus.ACTIVE)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["tenant_id", "code"], name="uq_department_code_tenant")]
        ordering = ["name"]


class Designation(TenantModel):
    """A firm-configurable job designation (e.g. Manager, Article Assistant).

    ``rank`` is an optional integer for ordering seniority in the UI; it confers
    no permission. Tenant-scoped unique ``code``.
    """

    name = models.CharField(max_length=160)
    code = models.CharField(max_length=30)
    description = models.TextField(blank=True)
    rank = models.PositiveIntegerField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=ActiveStatus.choices, default=ActiveStatus.ACTIVE)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["tenant_id", "code"], name="uq_designation_code_tenant")]
        ordering = ["rank", "name"]


class TeamMembership(TenantModel):
    """Additive many-team membership for an employee.

    Preserves ``Employee.team_id`` as the primary/home team; this model records
    additional team memberships with effective dates. A single active membership
    per (employee, team) is enforced by a conditional unique constraint.
    """

    employee_id = models.UUIDField(db_index=True)
    team_id = models.UUIDField(db_index=True)
    is_primary = models.BooleanField(default=False)
    effective_from = models.DateField(null=True, blank=True)
    effective_to = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["tenant_id", "employee_id", "team_id"],
                condition=models.Q(is_active=True),
                name="uq_active_team_membership",
            )
        ]
        ordering = ["-is_primary", "-effective_from"]


class ReportingRelationship(TenantModel):
    """Effective-dated reporting line for history and dotted-line reporting.

    ``relation_type`` distinguishes the solid primary line from dotted-line
    (functional) reporting. A current primary ``manager_id`` is also stored
    directly on Employee for efficient access; this model is the historical and
    dotted-line record. Self-reporting is rejected in the serializer, and a
    single active PRIMARY line per employee is enforced by a conditional unique
    constraint.
    """

    class RelationType(models.TextChoices):
        PRIMARY = "PRIMARY", "Primary"
        DOTTED = "DOTTED", "Dotted line"

    employee_id = models.UUIDField(db_index=True)
    manager_id = models.UUIDField(db_index=True)
    relation_type = models.CharField(max_length=10, choices=RelationType.choices, default=RelationType.PRIMARY)
    effective_from = models.DateField(null=True, blank=True)
    effective_to = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["tenant_id", "employee_id"],
                condition=models.Q(is_active=True, relation_type="PRIMARY"),
                name="uq_active_primary_reporting",
            )
        ]
        ordering = ["-effective_from"]
