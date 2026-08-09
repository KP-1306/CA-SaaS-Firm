from __future__ import annotations

from django.db import models

from core.db.models import TenantModel


class CatalogueStatus(models.TextChoices):
    ACTIVE = "ACTIVE", "Active"
    INACTIVE = "INACTIVE", "Inactive"


class RequirementSetStatus(models.TextChoices):
    DRAFT = "DRAFT", "Draft"
    ACTIVE = "ACTIVE", "Active"
    RETIRED = "RETIRED", "Retired"


class RequirementDocumentCategory(models.TextChoices):
    GST = "GST", "GST"
    TDS = "TDS", "TDS"
    INCOME_TAX = "INCOME_TAX", "Income Tax"
    ROC_MCA = "ROC_MCA", "ROC / MCA"
    AUDIT = "AUDIT", "Audit"
    ACCOUNTING = "ACCOUNTING", "Accounting"
    PAYROLL = "PAYROLL", "Payroll"
    BANKING = "BANKING", "Banking"
    REGISTRATION = "REGISTRATION", "Registration"
    IDENTITY_KYC = "IDENTITY_KYC", "Identity / KYC"
    LEGAL = "LEGAL", "Legal"
    OTHER = "OTHER", "Other"



class OperationalFieldType(models.TextChoices):
    TEXT = "TEXT", "Text"
    LONG_TEXT = "LONG_TEXT", "Long text"
    NUMBER = "NUMBER", "Number"
    DATE = "DATE", "Date"
    BOOLEAN = "BOOLEAN", "Yes / No"
    SELECT = "SELECT", "Selection"


class Vertical(TenantModel):
    name = models.CharField(max_length=160)
    code = models.CharField(max_length=40)
    description = models.TextField(blank=True)
    owner_user_id = models.UUIDField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=CatalogueStatus.choices, default=CatalogueStatus.ACTIVE)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["tenant_id", "code"], name="uq_vertical_code_tenant")]
        ordering = ["name"]


class Domain(TenantModel):
    vertical_id = models.UUIDField(db_index=True)
    name = models.CharField(max_length=160)
    code = models.CharField(max_length=40)
    description = models.TextField(blank=True)
    owner_user_id = models.UUIDField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=CatalogueStatus.choices, default=CatalogueStatus.ACTIVE)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["tenant_id", "vertical_id", "code"], name="uq_domain_code_vertical")]
        ordering = ["name"]


class Service(TenantModel):
    domain_id = models.UUIDField(db_index=True)
    name = models.CharField(max_length=180)
    code = models.CharField(max_length=50)
    description = models.TextField(blank=True)
    default_owner_user_id = models.UUIDField(null=True, blank=True)
    default_due_days = models.PositiveIntegerField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=CatalogueStatus.choices, default=CatalogueStatus.ACTIVE)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["tenant_id", "domain_id", "code"], name="uq_service_code_domain")]
        ordering = ["name"]


class ComplianceDeadlineRule(TenantModel):
    """Effective-dated statutory deadline rule for one configured service."""

    service_id = models.UUIDField(db_index=True)

    frequency = models.CharField(
        max_length=15,
        choices=[
            ("MONTHLY", "Monthly"),
            ("QUARTERLY", "Quarterly"),
            ("HALF_YEARLY", "Half yearly"),
            ("YEARLY", "Yearly"),
        ],
        db_index=True,
    )

    due_day = models.PositiveSmallIntegerField()
    due_month_offset = models.PositiveSmallIntegerField(
        default=0,
    )

    # Optional position within the recurrence cycle.
    #
    # NULL means the rule applies to every period for the frequency.
    # Examples:
    #   MONTHLY     -> 1..12
    #   QUARTERLY   -> 1..4
    #   HALF_YEARLY -> 1..2
    #   YEARLY      -> 1
    #
    # Period-specific rules allow statutory deadlines to vary between
    # periods without creating artificial services.
    period_number = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        db_index=True,
    )

    # Month in which this compliance cycle begins.
    #
    # 1 = calendar-year basis (Jan-Dec)
    # 4 = Indian financial-year basis (Apr-Mar)
    #
    # This controls period numbering for quarterly,
    # half-yearly and yearly statutory rules.
    period_start_month = models.PositiveSmallIntegerField(
        default=1,
    )

    effective_from = models.DateField(
        null=True,
        blank=True,
        db_index=True,
    )

    effective_until = models.DateField(
        null=True,
        blank=True,
        db_index=True,
    )

    is_active = models.BooleanField(
        default=True,
        db_index=True,
    )

    class Meta:
        ordering = [
            "service_id",
            "-effective_from",
            "-created_at",
        ]
        indexes = [
            models.Index(
                fields=[
                    "tenant_id",
                    "service_id",
                    "frequency",
                    "is_active",
                ],
                name="idx_deadline_rule_lookup",
            ),
        ]


class ServiceDocumentRequirementSet(TenantModel):
    """Versioned document checklist owned by one configured service.

    Historical sets are retained so work created under an older regulatory
    checklist can continue to use that checklist without being silently
    changed by later configuration updates.
    """

    service_id = models.UUIDField(db_index=True)
    name = models.CharField(max_length=180)
    version_number = models.PositiveIntegerField(default=1)
    effective_from = models.DateField(null=True, blank=True, db_index=True)
    effective_until = models.DateField(
        null=True,
        blank=True,
        db_index=True,
    )
    status = models.CharField(
        max_length=10,
        choices=RequirementSetStatus.choices,
        default=RequirementSetStatus.DRAFT,
        db_index=True,
    )
    description = models.TextField(blank=True)

    class Meta:
        ordering = [
            "service_id",
            "-version_number",
            "-effective_from",
        ]
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "tenant_id",
                    "service_id",
                    "version_number",
                ],
                name="uq_docreqset_service_version",
            ),
        ]
        indexes = [
            models.Index(
                fields=[
                    "tenant_id",
                    "service_id",
                    "status",
                ],
                name="idx_docreqset_service_status",
            ),
        ]


class ServiceDocumentRequirement(TenantModel):
    """One document definition inside a service requirement set."""

    requirement_set_id = models.UUIDField(db_index=True)
    service_id = models.UUIDField(db_index=True)

    name = models.CharField(max_length=200)
    code = models.CharField(max_length=60)
    description = models.TextField(blank=True)

    category = models.CharField(
        max_length=20,
        choices=RequirementDocumentCategory.choices,
        default=RequirementDocumentCategory.OTHER,
        db_index=True,
    )

    mandatory = models.BooleanField(default=True, db_index=True)
    display_order = models.PositiveIntegerField(default=10)

    financial_year_required = models.BooleanField(default=False)
    assessment_year_required = models.BooleanField(default=False)
    filing_period_required = models.BooleanField(default=False)

    expiry_applicable = models.BooleanField(default=False)
    expiry_reminder_days = models.PositiveIntegerField(
        null=True,
        blank=True,
    )

    requires_review = models.BooleanField(default=True)
    allow_multiple_versions = models.BooleanField(default=True)
    allow_multiple_files = models.BooleanField(default=False)

    allowed_extensions = models.CharField(
        max_length=250,
        blank=True,
        help_text=(
            "Comma-separated extensions, for example: "
            "pdf,xlsx,xls,csv"
        ),
    )
    maximum_file_size_mb = models.PositiveIntegerField(default=15)

    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        ordering = [
            "display_order",
            "name",
        ]
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "tenant_id",
                    "requirement_set_id",
                    "code",
                ],
                name="uq_docrequirement_set_code",
            ),
        ]
        indexes = [
            models.Index(
                fields=[
                    "tenant_id",
                    "service_id",
                    "is_active",
                ],
                name="idx_docreq_service_active",
            ),
            models.Index(
                fields=[
                    "tenant_id",
                    "requirement_set_id",
                    "display_order",
                ],
                name="idx_docrequirement_set_order",
            ),
        ]


class ServiceOperationalField(TenantModel):
    """
    One operational field shown for work belonging to a service.

    The field definition belongs to the service catalogue. Individual values
    are stored on WorkItem.operational_data.
    """

    service_id = models.UUIDField(db_index=True)
    key = models.CharField(max_length=80)
    label = models.CharField(max_length=180)
    field_type = models.CharField(
        max_length=20,
        choices=OperationalFieldType.choices,
        default=OperationalFieldType.TEXT,
    )
    help_text = models.TextField(blank=True)
    placeholder = models.CharField(max_length=200, blank=True)
    required = models.BooleanField(default=False, db_index=True)
    options = models.JSONField(default=list, blank=True)
    display_order = models.PositiveIntegerField(default=10)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        ordering = ["display_order", "label", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant_id", "service_id", "key"],
                name="uq_service_operational_field_key",
            ),
        ]
        indexes = [
            models.Index(
                fields=[
                    "tenant_id",
                    "service_id",
                    "is_active",
                    "display_order",
                ],
                name="idx_service_operational_fields",
            ),
        ]
