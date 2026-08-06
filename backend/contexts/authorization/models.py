from django.db import models


# =============================================================================
# Phase 3B Authorization Foundation
# =============================================================================


class RoleTemplate(models.Model):
    """
    Business role template.
    """

    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    is_system = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "authorization_role_template"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Access(models.Model):
    """
    Individual business capability.
    """

    module = models.CharField(max_length=100)
    code = models.CharField(max_length=150, unique=True)
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "authorization_access"
        ordering = ["module", "name"]

    def __str__(self):
        return self.name


class RoleAccess(models.Model):
    """
    Role -> Access mapping.
    """

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

    class Meta:
        db_table = "authorization_role_access"
        unique_together = [("role", "access")]


class AccessProfile(models.Model):
    """
    User access profile.

    Relationships will be completed
    in the next engineering slice.
    """

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "authorization_access_profile"
