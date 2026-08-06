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

# --- Phase 3A.1 Vridhi consultant authentication foundation ---

import hashlib

from django.contrib.auth.hashers import check_password, make_password
from django.utils import timezone

from core.db.uuid7 import uuid7


class UserAccountStatus(models.TextChoices):
    ACTIVE = "ACTIVE", "Active"
    SUSPENDED = "SUSPENDED", "Suspended"
    DISABLED = "DISABLED", "Disabled"


class ProviderRole(models.TextChoices):
    PLATFORM_ADMIN = "PLATFORM_ADMIN", "Platform administrator"
    OPERATIONS_ADMIN = "OPERATIONS_ADMIN", "Operations administrator"
    IMPLEMENTATION_CONSULTANT = "IMPLEMENTATION_CONSULTANT", "Implementation consultant"
    SUPPORT_CONSULTANT = "SUPPORT_CONSULTANT", "Support consultant"
    SECURITY_AUDITOR = "SECURITY_AUDITOR", "Security auditor"


class MembershipStatus(models.TextChoices):
    ACTIVE = "ACTIVE", "Active"
    SUSPENDED = "SUSPENDED", "Suspended"
    ENDED = "ENDED", "Ended"


class AuthenticationEventType(models.TextChoices):
    LOGIN_SUCCEEDED = "LOGIN_SUCCEEDED", "Login succeeded"
    LOGIN_FAILED = "LOGIN_FAILED", "Login failed"
    LOGOUT = "LOGOUT", "Logout"
    SESSION_CREATED = "SESSION_CREATED", "Session created"
    SESSION_REVOKED = "SESSION_REVOKED", "Session revoked"
    ACCESS_DENIED = "ACCESS_DENIED", "Access denied"
    PASSWORD_CHANGED = "PASSWORD_CHANGED", "Password changed"
    ACCOUNT_STATUS_CHANGED = "ACCOUNT_STATUS_CHANGED", "Account status changed"
    MEMBERSHIP_CHANGED = "MEMBERSHIP_CHANGED", "Membership changed"


class AuthenticationOutcome(models.TextChoices):
    SUCCESS = "SUCCESS", "Success"
    FAILURE = "FAILURE", "Failure"
    DENIED = "DENIED", "Denied"


class UserAccount(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    email = models.EmailField(unique=True)
    display_name = models.CharField(max_length=180)
    password_hash = models.CharField(max_length=255)
    status = models.CharField(
        max_length=12,
        choices=UserAccountStatus.choices,
        default=UserAccountStatus.ACTIVE,
        db_index=True,
    )
    email_verified_at = models.DateTimeField(null=True, blank=True)
    failed_login_count = models.PositiveIntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)
    last_login_at = models.DateTimeField(null=True, blank=True)
    password_changed_at = models.DateTimeField(null=True, blank=True)
    must_change_password = models.BooleanField(default=False)
    invitation_sent_at = models.DateTimeField(null=True, blank=True)
    invited_by_principal_id = models.UUIDField(null=True, blank=True)
    activated_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["email"]

    def save(self, *args, **kwargs):
        self.email = (self.email or "").strip().lower()
        super().save(*args, **kwargs)

    def set_password(self, raw_password: str) -> None:
        self.password_hash = make_password(raw_password)
        self.password_changed_at = timezone.now()

    def check_password(self, raw_password: str) -> bool:
        return check_password(raw_password, self.password_hash)

    @property
    def is_authenticated(self) -> bool:
        return True


class ProviderMembership(TenantModel):
    user_account_id = models.UUIDField(db_index=True)
    employee_id = models.UUIDField(null=True, blank=True, db_index=True)
    role = models.CharField(max_length=32, choices=ProviderRole.choices)
    status = models.CharField(
        max_length=12,
        choices=MembershipStatus.choices,
        default=MembershipStatus.ACTIVE,
        db_index=True,
    )
    effective_from = models.DateTimeField(default=timezone.now)
    effective_to = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["tenant_id", "user_account_id"],
                condition=models.Q(status=MembershipStatus.ACTIVE),
                name="uq_active_provider_membership",
            )
        ]
        ordering = ["user_account_id"]


class AuthSession(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    user_account_id = models.UUIDField(db_index=True)
    membership_id = models.UUIDField(db_index=True)
    tenant_id = models.UUIDField(db_index=True)
    principal_id = models.UUIDField(db_index=True)
    token_hash = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField(db_index=True)
    revoked_at = models.DateTimeField(null=True, blank=True, db_index=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent_hash = models.CharField(max_length=64, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["user_account_id", "revoked_at"]),
            models.Index(fields=["tenant_id", "expires_at"]),
        ]
        ordering = ["-created_at"]

    @staticmethod
    def digest(raw_token: str) -> str:
        return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

    @property
    def is_active(self) -> bool:
        return self.revoked_at is None and self.expires_at > timezone.now()


class AuthenticationEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    occurred_at = models.DateTimeField(auto_now_add=True, db_index=True)
    tenant_id = models.UUIDField(null=True, blank=True, db_index=True)
    user_account_id = models.UUIDField(null=True, blank=True, db_index=True)
    principal_id = models.UUIDField(null=True, blank=True, db_index=True)
    session_id = models.UUIDField(null=True, blank=True, db_index=True)
    event_type = models.CharField(max_length=32, choices=AuthenticationEventType.choices, db_index=True)
    outcome = models.CharField(max_length=10, choices=AuthenticationOutcome.choices, db_index=True)
    email = models.EmailField(blank=True)
    reason = models.CharField(max_length=200, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=300, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-occurred_at"]
        indexes = [
            models.Index(fields=["tenant_id", "occurred_at"]),
            models.Index(fields=["event_type", "outcome"]),
        ]

    def save(self, *args, **kwargs):
        if self.pk and AuthenticationEvent.objects.filter(pk=self.pk).exists():
            raise RuntimeError("Authentication events are append-only.")
        self.email = (self.email or "").strip().lower()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise RuntimeError("Authentication events are append-only.")
