from __future__ import annotations

from django.db import models

from core.db.models import TenantModel


class ClientType(models.TextChoices):
    INDIVIDUAL = "INDIVIDUAL", "Individual"
    PROPRIETORSHIP = "PROPRIETORSHIP", "Proprietorship"
    PARTNERSHIP = "PARTNERSHIP", "Partnership"
    LLP = "LLP", "LLP"
    PRIVATE_LIMITED = "PRIVATE_LIMITED", "Private Limited Company"
    PUBLIC_LIMITED = "PUBLIC_LIMITED", "Public Limited Company"
    TRUST = "TRUST", "Trust"
    OTHER = "OTHER", "Other"


class EngagementStatus(models.TextChoices):
    ACTIVE = "ACTIVE", "Active"
    PROSPECT = "PROSPECT", "Prospect"
    ON_HOLD = "ON_HOLD", "On hold"
    INACTIVE = "INACTIVE", "Inactive"


class ContactChannel(models.TextChoices):
    WHATSAPP = "WHATSAPP", "WhatsApp"
    EMAIL = "EMAIL", "Email"
    PHONE = "PHONE", "Phone"
    PORTAL = "PORTAL", "Portal"
    MANUAL = "MANUAL", "Manual"


class ClientLifecycleStatus(models.TextChoices):
    """Explicit client lifecycle (additive; distinct from engagement_status).

    engagement_status remains the existing relationship-health field. This new
    field formalises the operational lifecycle required by the milestone and is
    never a silent reuse of engagement_status.
    """

    PROSPECT = "PROSPECT", "Prospect"
    ONBOARDING = "ONBOARDING", "Onboarding"
    ACTIVE = "ACTIVE", "Active"
    SUSPENDED = "SUSPENDED", "Suspended"
    CLOSED = "CLOSED", "Closed"
    ARCHIVED = "ARCHIVED", "Archived"


class Client(TenantModel):
    legal_name = models.CharField(max_length=250)
    trade_name = models.CharField(max_length=250, blank=True)
    client_type = models.CharField(max_length=25, choices=ClientType.choices)
    industry = models.CharField(max_length=120, blank=True)
    pan = models.CharField(max_length=10, blank=True)
    cin_or_llpin = models.CharField(max_length=30, blank=True)
    registered_address = models.TextField(blank=True)
    relationship_manager_id = models.UUIDField(null=True, blank=True)
    engagement_status = models.CharField(max_length=15, choices=EngagementStatus.choices, default=EngagementStatus.ACTIVE)
    notes = models.TextField(blank=True)

    # --- Client lifecycle (additive; V1 Core Workflow + Client Management) ---
    tan = models.CharField(max_length=10, blank=True)
    lifecycle_status = models.CharField(
        max_length=15,
        choices=ClientLifecycleStatus.choices,
        default=ClientLifecycleStatus.PROSPECT,
        db_index=True,
    )
    primary_branch_id = models.UUIDField(null=True, blank=True, db_index=True)
    primary_contact_id = models.UUIDField(null=True, blank=True, db_index=True)
    onboarding_date = models.DateField(null=True, blank=True)
    activation_date = models.DateField(null=True, blank=True)
    suspension_date = models.DateField(null=True, blank=True)
    suspension_reason = models.TextField(blank=True)
    closure_date = models.DateField(null=True, blank=True)
    closure_reason = models.TextField(blank=True)
    archive_date = models.DateField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["tenant_id", "pan"], condition=~models.Q(pan=""), name="uq_client_pan_tenant")]
        ordering = ["legal_name"]

    @property
    def name(self) -> str:
        return self.trade_name or self.legal_name


class ClientContact(TenantModel):
    client_id = models.UUIDField(db_index=True)
    name = models.CharField(max_length=180)
    designation = models.CharField(max_length=100, blank=True)
    email = models.EmailField(blank=True)
    mobile = models.CharField(max_length=20, blank=True)
    whatsapp_number = models.CharField(max_length=20, blank=True)
    preferred_channel = models.CharField(max_length=12, choices=ContactChannel.choices, default=ContactChannel.WHATSAPP)
    can_receive_document_requests = models.BooleanField(default=True)
    is_primary = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-is_primary", "name"]


class ClientGSTRegistration(TenantModel):
    client_id = models.UUIDField(db_index=True)
    gstin = models.CharField(max_length=15)
    state = models.CharField(max_length=100, blank=True)
    trade_name = models.CharField(max_length=250, blank=True)
    address = models.TextField(blank=True)
    is_primary = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["tenant_id", "gstin"], name="uq_client_gstin_tenant")]
        ordering = ["-is_primary", "gstin"]


class ClientBranch(TenantModel):
    client_id = models.UUIDField(db_index=True)
    name = models.CharField(max_length=160)
    address = models.TextField(blank=True)
    state = models.CharField(max_length=100, blank=True)
    contact_name = models.CharField(max_length=180, blank=True)
    contact_mobile = models.CharField(max_length=20, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
