from django.db import models


class RoleTemplate(models.Model):
    """Simple business role used to configure user access."""

    tenant_id = models.UUIDField(
        null=True,
        blank=True,
        db_index=True,
        help_text="Blank for Vridhi system templates.",
    )
    code = models.CharField(max_length=50, null=True, blank=True)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    is_system = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)

    class Meta:
        db_table = "authorization_role_template"
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant_id", "code"],
                name="uq_auth_role_tenant_code",
            ),
            models.UniqueConstraint(
                fields=["code"],
                condition=models.Q(tenant_id__isnull=True),
                name="uq_auth_system_role_code",
            ),
        ]

    def __str__(self) -> str:
        return self.name


class Access(models.Model):
    """One business capability, grouped by product module."""

    module = models.CharField(max_length=100, db_index=True)
    code = models.CharField(max_length=150, unique=True)
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)

    class Meta:
        db_table = "authorization_access"
        ordering = ["module", "name"]

    def __str__(self) -> str:
        return self.name


class RoleAccess(models.Model):
    """Access included automatically through a role template."""

    role = models.ForeignKey(
        RoleTemplate,
        on_delete=models.CASCADE,
        related_name="role_access",
    )
    access = models.ForeignKey(
        Access,
        on_delete=models.CASCADE,
        related_name="access_roles",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "authorization_role_access"
        constraints = [
            models.UniqueConstraint(
                fields=["role", "access"],
                name="uq_auth_role_access",
            )
        ]


class AccessProfile(models.Model):
    """
    Tenant-specific access configuration for one authenticated UserAccount.

    Organisational and service references remain UUID values so authorization
    does not duplicate or own records from other bounded contexts.
    """

    tenant_id = models.UUIDField(
        null=True,
        blank=True,
        db_index=True,
    )
    user_account_id = models.UUIDField(
        null=True,
        blank=True,
        db_index=True,
    )

    role = models.ForeignKey(
        RoleTemplate,
        on_delete=models.PROTECT,
        related_name="access_profiles",
        null=True,
        blank=True,
    )

    department_ids = models.JSONField(default=list, blank=True)
    team_ids = models.JSONField(default=list, blank=True)
    service_ids = models.JSONField(default=list, blank=True)

    additional_access = models.ManyToManyField(
        Access,
        blank=True,
        related_name="additional_profiles",
    )

    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)

    class Meta:
        db_table = "authorization_access_profile"
        ordering = ["tenant_id", "user_account_id"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant_id", "user_account_id"],
                name="uq_auth_profile_tenant_user",
            )
        ]

    def __str__(self) -> str:
        return f"{self.tenant_id}:{self.user_account_id}"
