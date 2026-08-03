from __future__ import annotations

from django.db import models

from core.db.models import TenantModel


class FirmRole(models.TextChoices):
    ADMIN = "ADMIN", "Admin"
    PARTNER = "PARTNER", "Partner"
    MANAGER = "MANAGER", "Manager"
    STAFF = "STAFF", "Staff"
    READ_ONLY = "READ_ONLY", "Read only"


class EmploymentType(models.TextChoices):
    """Employment type. Descriptive; confers no authority."""

    FULL_TIME = "FULL_TIME", "Full time"
    PART_TIME = "PART_TIME", "Part time"
    ARTICLE = "ARTICLE", "Article assistant"
    INTERN = "INTERN", "Intern"
    CONTRACT = "CONTRACT", "Contract"
    CONSULTANT = "CONSULTANT", "Consultant"


class EmploymentStatus(models.TextChoices):
    """Employment lifecycle status. Independent of ``is_active`` login gating."""

    PROBATION = "PROBATION", "Probation"
    CONFIRMED = "CONFIRMED", "Confirmed"
    NOTICE_PERIOD = "NOTICE_PERIOD", "Notice period"
    EXITED = "EXITED", "Exited"
    SUSPENDED = "SUSPENDED", "Suspended"


class Employee(TenantModel):
    name = models.CharField(max_length=180)
    email = models.EmailField()
    mobile = models.CharField(max_length=20, blank=True)
    employee_code = models.CharField(max_length=40, blank=True)
    role = models.CharField(max_length=20, choices=FirmRole.choices, default=FirmRole.STAFF)
    branch_id = models.UUIDField(null=True, blank=True)
    team_id = models.UUIDField(null=True, blank=True)
    expertise = models.JSONField(default=list, blank=True)
    is_active = models.BooleanField(default=True)
    principal_id = models.UUIDField(null=True, blank=True, db_index=True)

    # --- Employee Operations V1 employment fields (additive) ---
    department_id = models.UUIDField(null=True, blank=True, db_index=True)
    designation_id = models.UUIDField(null=True, blank=True, db_index=True)
    manager_id = models.UUIDField(null=True, blank=True, db_index=True)
    employment_type = models.CharField(max_length=15, choices=EmploymentType.choices, blank=True)
    employment_status = models.CharField(max_length=15, choices=EmploymentStatus.choices, blank=True)
    joining_date = models.DateField(null=True, blank=True)
    confirmation_date = models.DateField(null=True, blank=True)
    exit_date = models.DateField(null=True, blank=True)
    timezone = models.CharField(max_length=64, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["tenant_id", "email"], name="uq_employee_email_tenant"),
            models.UniqueConstraint(
                fields=["tenant_id", "employee_code"],
                condition=~models.Q(employee_code=""),
                name="uq_employee_code_tenant",
            ),
        ]
        ordering = ["name"]


class ExpertiseCategory(models.TextChoices):
    GST = "GST", "GST"
    INCOME_TAX = "INCOME_TAX", "Income Tax"
    TDS = "TDS", "TDS"
    ROC = "ROC", "ROC"
    STATUTORY_AUDIT = "STATUTORY_AUDIT", "Statutory Audit"
    INTERNAL_AUDIT = "INTERNAL_AUDIT", "Internal Audit"
    TAX_AUDIT = "TAX_AUDIT", "Tax Audit"
    BANK_AUDIT = "BANK_AUDIT", "Bank Audit"
    CONCURRENT_AUDIT = "CONCURRENT_AUDIT", "Concurrent Audit"
    ACCOUNTING = "ACCOUNTING", "Accounting"
    BOOKKEEPING = "BOOKKEEPING", "Bookkeeping"
    PAYROLL = "PAYROLL", "Payroll"
    COMPLIANCE = "COMPLIANCE", "Compliance"
    COMPANY_FORMATION = "COMPANY_FORMATION", "Company Formation"
    PROJECT_FINANCE = "PROJECT_FINANCE", "Project Finance"
    MSME = "MSME", "MSME"
    FEMA = "FEMA", "FEMA"
    INTERNATIONAL_TAX = "INTERNATIONAL_TAX", "International Tax"
    NRI_TAXATION = "NRI_TAXATION", "NRI Taxation"
    TRANSFER_PRICING = "TRANSFER_PRICING", "Transfer Pricing"


class ProficiencyLevel(models.TextChoices):
    """Approved five-level proficiency vocabulary (Employee Operations V1).

    The legacy four-level data (BASIC/INTERMEDIATE/ADVANCED/EXPERT) is migrated
    reversibly into this vocabulary: BASIC -> BEGINNER, EXPERT -> SME,
    INTERMEDIATE/ADVANCED unchanged. REVIEWER is a new top level indicating
    review authority for the category.
    """

    BEGINNER = "BEGINNER", "Beginner"
    INTERMEDIATE = "INTERMEDIATE", "Intermediate"
    ADVANCED = "ADVANCED", "Advanced"
    SME = "SME", "Subject matter expert"
    REVIEWER = "REVIEWER", "Reviewer"


class SkillCatalogue(TenantModel):
    """Tenant-configurable skill/dimension catalogue.

    Seeded from the fixed ``ExpertiseCategory`` values but extensible with
    firm-defined custom skills. ``category_key`` holds the canonical enum value
    for seeded rows, or a firm-defined slug for custom skills. Tenant-scoped
    unique ``code``.
    """

    name = models.CharField(max_length=160)
    code = models.CharField(max_length=40)
    category_key = models.CharField(max_length=40, blank=True)
    description = models.TextField(blank=True)
    is_custom = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["tenant_id", "code"], name="uq_skill_code_tenant")]
        ordering = ["name"]


class EmployeeExpertise(TenantModel):
    """Normalized employee expertise (replaces the legacy JSON list for writes).

    ``employee_id`` is a UUID reference (cross-row integrity on
    ``(tenant_id, id)``), consistent with the platform's no-cross-FK rule.
    A single ACTIVE expertise entry per (employee, category) is enforced by a
    conditional unique constraint; historical (inactive) rows may coexist.

    Employee Operations V1 extends this model additively with effective dates,
    certification, reviewer eligibility, experience duration, evidence and
    review-tracking. Existing rows keep working: every new column is
    nullable/blank or safely defaulted, and ``is_active`` defaults True so the
    new conditional unique matches the old absolute one for current data.
    """

    employee_id = models.UUIDField(db_index=True)
    category = models.CharField(max_length=30, choices=ExpertiseCategory.choices)
    proficiency = models.CharField(
        max_length=15, choices=ProficiencyLevel.choices, default=ProficiencyLevel.INTERMEDIATE
    )

    # --- Employee Operations V1 extensions (additive) ---
    skill_id = models.UUIDField(null=True, blank=True, db_index=True)
    custom_label = models.CharField(max_length=160, blank=True)
    experience_months = models.PositiveIntegerField(null=True, blank=True)
    certification = models.CharField(max_length=200, blank=True)
    is_primary = models.BooleanField(default=False)
    reviewer_eligible = models.BooleanField(default=False)
    effective_from = models.DateField(null=True, blank=True)
    effective_to = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    evidence = models.TextField(blank=True)
    last_reviewed_date = models.DateField(null=True, blank=True)
    reviewed_by = models.UUIDField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["tenant_id", "employee_id", "category"],
                condition=models.Q(is_active=True),
                name="uq_employee_expertise_active_category",
            )
        ]
        ordering = ["category"]
