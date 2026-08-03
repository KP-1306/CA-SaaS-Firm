from __future__ import annotations

from rest_framework import serializers

from .models import (
    Domain,
    Service,
    ServiceDocumentRequirement,
    ServiceDocumentRequirementSet,
    Vertical,
)


class VerticalSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vertical
        fields = "__all__"
        read_only_fields = ("id", "tenant_id", "created_at", "created_by", "updated_at", "updated_by", "row_version")

class DomainSerializer(serializers.ModelSerializer):
    class Meta:
        model = Domain
        fields = "__all__"
        read_only_fields = ("id", "tenant_id", "created_at", "created_by", "updated_at", "updated_by", "row_version")

class ServiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Service
        fields = "__all__"
        read_only_fields = ("id", "tenant_id", "created_at", "created_by", "updated_at", "updated_by", "row_version")


class ServiceDocumentRequirementSetSerializer(
    serializers.ModelSerializer
):
    requirement_count = serializers.SerializerMethodField()
    mandatory_count = serializers.SerializerMethodField()

    class Meta:
        model = ServiceDocumentRequirementSet
        fields = "__all__"
        read_only_fields = (
            "id",
            "tenant_id",
            "created_at",
            "created_by",
            "updated_at",
            "updated_by",
            "row_version",
        )
        validators = []

    def validate(self, attrs):
        instance = getattr(self, "instance", None)

        service_id = attrs.get(
            "service_id",
            getattr(instance, "service_id", None),
        )

        version_number = attrs.get(
            "version_number",
            getattr(instance, "version_number", 1),
        )

        effective_from = attrs.get(
            "effective_from",
            getattr(instance, "effective_from", None),
        )

        effective_until = attrs.get(
            "effective_until",
            getattr(instance, "effective_until", None),
        )

        if (
            effective_from
            and effective_until
            and effective_until < effective_from
        ):
            raise serializers.ValidationError(
                {
                    "effective_until": (
                        "Effective until cannot be earlier than "
                        "effective from."
                    )
                }
            )

        request = self.context.get("request")
        tenant_id = (
            getattr(getattr(request, "user", None), "tenant_id", None)
            if request
            else None
        )

        duplicate = (
            ServiceDocumentRequirementSet.objects.filter(
                tenant_id=tenant_id,
                service_id=service_id,
                version_number=version_number,
            )
        )

        if instance is not None:
            duplicate = duplicate.exclude(pk=instance.pk)

        if duplicate.exists():
            raise serializers.ValidationError(
                {
                    "version_number": (
                        "This version already exists for the selected "
                        "service."
                    )
                }
            )

        return attrs

    @staticmethod
    def get_requirement_count(obj):
        return ServiceDocumentRequirement.objects.filter(
            tenant_id=obj.tenant_id,
            requirement_set_id=obj.id,
            is_active=True,
        ).count()

    @staticmethod
    def get_mandatory_count(obj):
        return ServiceDocumentRequirement.objects.filter(
            tenant_id=obj.tenant_id,
            requirement_set_id=obj.id,
            is_active=True,
            mandatory=True,
        ).count()


class ServiceDocumentRequirementSerializer(
    serializers.ModelSerializer
):
    requirement_set_name = serializers.SerializerMethodField()
    requirement_set_version = serializers.SerializerMethodField()

    class Meta:
        model = ServiceDocumentRequirement
        fields = "__all__"
        read_only_fields = (
            "id",
            "tenant_id",
            "created_at",
            "created_by",
            "updated_at",
            "updated_by",
            "row_version",
        )
        validators = []

    def validate(self, attrs):
        instance = getattr(self, "instance", None)

        requirement_set_id = attrs.get(
            "requirement_set_id",
            getattr(instance, "requirement_set_id", None),
        )

        service_id = attrs.get(
            "service_id",
            getattr(instance, "service_id", None),
        )

        code = (
            attrs.get(
                "code",
                getattr(instance, "code", ""),
            )
            or ""
        ).strip().upper()

        name = (
            attrs.get(
                "name",
                getattr(instance, "name", ""),
            )
            or ""
        ).strip()

        attrs["code"] = code
        attrs["name"] = name

        request = self.context.get("request")
        tenant_id = (
            getattr(getattr(request, "user", None), "tenant_id", None)
            if request
            else None
        )

        requirement_set = (
            ServiceDocumentRequirementSet.objects.filter(
                tenant_id=tenant_id,
                id=requirement_set_id,
                service_id=service_id,
            ).first()
        )

        if requirement_set is None:
            raise serializers.ValidationError(
                {
                    "requirement_set_id": (
                        "The selected requirement set does not belong "
                        "to the selected service."
                    )
                }
            )

        duplicate = ServiceDocumentRequirement.objects.filter(
            tenant_id=tenant_id,
            requirement_set_id=requirement_set_id,
            code=code,
        )

        if instance is not None:
            duplicate = duplicate.exclude(pk=instance.pk)

        if duplicate.exists():
            raise serializers.ValidationError(
                {
                    "code": (
                        "A document requirement with this code already "
                        "exists in the selected set."
                    )
                }
            )

        expiry_applicable = attrs.get(
            "expiry_applicable",
            getattr(instance, "expiry_applicable", False),
        )

        reminder_days = attrs.get(
            "expiry_reminder_days",
            getattr(instance, "expiry_reminder_days", None),
        )

        if not expiry_applicable:
            attrs["expiry_reminder_days"] = None
        elif reminder_days is None:
            attrs["expiry_reminder_days"] = 30

        return attrs

    @staticmethod
    def _requirement_set(obj):
        return ServiceDocumentRequirementSet.objects.filter(
            tenant_id=obj.tenant_id,
            id=obj.requirement_set_id,
        ).first()

    def get_requirement_set_name(self, obj):
        requirement_set = self._requirement_set(obj)
        return requirement_set.name if requirement_set else ""

    def get_requirement_set_version(self, obj):
        requirement_set = self._requirement_set(obj)
        return (
            requirement_set.version_number
            if requirement_set
            else None
        )
