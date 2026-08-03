from __future__ import annotations

from rest_framework import serializers

from .models import Employee, EmployeeExpertise, SkillCatalogue

_AUDIT = ("id", "tenant_id", "created_at", "created_by", "updated_at", "updated_by", "row_version")


def _tenant_id(serializer):
    request = serializer.context.get("request")
    principal = getattr(request, "principal", None) if request else None
    return (
        getattr(serializer.instance, "tenant_id", None)
        or getattr(principal, "tenant_id", None)
        or (request.META.get("HTTP_X_TENANT_ID") if request else None)
    )


class SkillCatalogueSerializer(serializers.ModelSerializer):
    class Meta:
        model = SkillCatalogue
        fields = "__all__"
        read_only_fields = _AUDIT


class EmployeeExpertiseSerializer(serializers.ModelSerializer):
    category_label = serializers.SerializerMethodField()
    proficiency_label = serializers.SerializerMethodField()

    class Meta:
        model = EmployeeExpertise
        fields = "__all__"
        read_only_fields = _AUDIT

    @staticmethod
    def get_category_label(obj):
        return obj.get_category_display()

    @staticmethod
    def get_proficiency_label(obj):
        return obj.get_proficiency_display()


class EmployeeSerializer(serializers.ModelSerializer):
    expertise_records = serializers.SerializerMethodField()

    class Meta:
        model = Employee
        fields = "__all__"
        read_only_fields = _AUDIT
        # Conditional tenant constraints must not make employee_code required.
        extra_kwargs = {
            "employee_code": {
                "required": False,
                "allow_blank": True,
            }
        }
        # Tenant is injected by the viewset after serializer validation, so
        # perform explicit tenant-aware checks below.
        validators = []

    def validate(self, attrs):
        instance = getattr(self, "instance", None)
        tenant_id = _tenant_id(self)

        email = attrs.get(
            "email", getattr(instance, "email", "") if instance else ""
        )
        normalised_email = (email or "").strip().lower()
        attrs["email"] = normalised_email

        employee_code = attrs.get(
            "employee_code",
            getattr(instance, "employee_code", "") if instance else "",
        )
        normalised_code = (employee_code or "").strip().upper()
        attrs["employee_code"] = normalised_code

        duplicate_email = Employee.objects.filter(
            tenant_id=tenant_id,
            email__iexact=normalised_email,
        )
        if instance is not None:
            duplicate_email = duplicate_email.exclude(pk=instance.pk)
        if normalised_email and duplicate_email.exists():
            raise serializers.ValidationError(
                {"email": "An employee with this email already exists for the firm."}
            )

        if normalised_code:
            duplicate_code = Employee.objects.filter(
                tenant_id=tenant_id,
                employee_code=normalised_code,
            )
            if instance is not None:
                duplicate_code = duplicate_code.exclude(pk=instance.pk)
            if duplicate_code.exists():
                raise serializers.ValidationError(
                    {
                        "employee_code": (
                            "An employee with this code already exists for the firm."
                        )
                    }
                )

        return attrs

    def get_expertise_records(self, obj):
        records = EmployeeExpertise.objects.filter(
            tenant_id=obj.tenant_id,
            employee_id=obj.id,
        )
        return EmployeeExpertiseSerializer(records, many=True).data
