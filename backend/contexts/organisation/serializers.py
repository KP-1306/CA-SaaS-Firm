from __future__ import annotations

from rest_framework import serializers

from .models import (
    Branch,
    Department,
    Designation,
    FirmProfile,
    ReportingRelationship,
    Team,
    TeamMembership,
)

_AUDIT = ("id", "tenant_id", "created_at", "created_by", "updated_at", "updated_by", "row_version")


def _tenant_id(serializer):
    request = serializer.context.get("request")
    principal = getattr(request, "principal", None) if request else None
    return (
        getattr(serializer.instance, "tenant_id", None)
        or getattr(principal, "tenant_id", None)
        or (request.META.get("HTTP_X_TENANT_ID") if request else None)
    )


class FirmProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = FirmProfile
        fields = "__all__"
        read_only_fields = _AUDIT


class BranchSerializer(serializers.ModelSerializer):
    class Meta:
        model = Branch
        fields = "__all__"
        read_only_fields = _AUDIT


class TeamSerializer(serializers.ModelSerializer):
    class Meta:
        model = Team
        fields = "__all__"
        read_only_fields = _AUDIT


class DepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = "__all__"
        read_only_fields = _AUDIT
        validators = []

    def validate(self, attrs):
        instance = getattr(self, "instance", None)
        code = attrs.get("code", getattr(instance, "code", "") if instance else "")
        normalised = (code or "").strip().upper()
        attrs["code"] = normalised

        duplicate = Department.objects.filter(
            tenant_id=_tenant_id(self),
            code=normalised,
        )
        if instance is not None:
            duplicate = duplicate.exclude(pk=instance.pk)
        if normalised and duplicate.exists():
            raise serializers.ValidationError(
                {"code": "A department with this code already exists for the firm."}
            )
        return attrs


class DesignationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Designation
        fields = "__all__"
        read_only_fields = _AUDIT
        validators = []

    def validate(self, attrs):
        instance = getattr(self, "instance", None)
        code = attrs.get("code", getattr(instance, "code", "") if instance else "")
        normalised = (code or "").strip().upper()
        attrs["code"] = normalised

        duplicate = Designation.objects.filter(
            tenant_id=_tenant_id(self),
            code=normalised,
        )
        if instance is not None:
            duplicate = duplicate.exclude(pk=instance.pk)
        if normalised and duplicate.exists():
            raise serializers.ValidationError(
                {"code": "A designation with this code already exists for the firm."}
            )
        return attrs


class TeamMembershipSerializer(serializers.ModelSerializer):
    class Meta:
        model = TeamMembership
        fields = "__all__"
        read_only_fields = _AUDIT
        validators = []

    def validate(self, attrs):
        instance = getattr(self, "instance", None)
        employee_id = attrs.get(
            "employee_id",
            getattr(instance, "employee_id", None) if instance else None,
        )
        team_id = attrs.get(
            "team_id",
            getattr(instance, "team_id", None) if instance else None,
        )
        is_active = attrs.get(
            "is_active",
            getattr(instance, "is_active", True) if instance else True,
        )

        if is_active:
            duplicate = TeamMembership.objects.filter(
                tenant_id=_tenant_id(self),
                employee_id=employee_id,
                team_id=team_id,
                is_active=True,
            )
            if instance is not None:
                duplicate = duplicate.exclude(pk=instance.pk)
            if duplicate.exists():
                raise serializers.ValidationError(
                    {
                        "team_id": (
                            "This employee already has an active membership "
                            "for this team."
                        )
                    }
                )
        return attrs


class ReportingRelationshipSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReportingRelationship
        fields = "__all__"
        read_only_fields = _AUDIT

    def validate(self, attrs):
        """Prevent self-reporting (deep cycle prevention is done in the viewset)."""
        instance = getattr(self, "instance", None)
        employee_id = attrs.get("employee_id", getattr(instance, "employee_id", None))
        manager_id = attrs.get("manager_id", getattr(instance, "manager_id", None))
        if employee_id is not None and manager_id is not None and employee_id == manager_id:
            raise serializers.ValidationError(
                {"manager_id": "An employee cannot report to themselves."}
            )
        return attrs
