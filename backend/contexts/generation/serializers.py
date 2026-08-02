"""Serializers for the generation context.

Follows the platform convention exactly: ``ModelSerializer`` with
``fields="__all__"`` and the 7 audit fields read-only. No raw-UUID text inputs
are introduced on the frontend; UUID references are selected via existing
pickers, matching the client/work screens.
"""

from __future__ import annotations

from rest_framework import serializers

from .models import (
    ClientServiceSubscription,
    GeneratedWorkLedger,
    RecurringWorkProfile,
    TaskTemplate,
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


class ClientServiceSubscriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClientServiceSubscription
        fields = "__all__"
        read_only_fields = _AUDIT
        # Validate explicitly because tenant_id is injected by the viewset only
        # after serializer validation.
        validators = []

    def validate(self, attrs):
        instance = getattr(self, "instance", None)
        client_id = attrs.get(
            "client_id", getattr(instance, "client_id", None) if instance else None
        )
        service_id = attrs.get(
            "service_id", getattr(instance, "service_id", None) if instance else None
        )
        duplicate = ClientServiceSubscription.objects.filter(
            tenant_id=_tenant_id(self),
            client_id=client_id,
            service_id=service_id,
        )
        if instance is not None:
            duplicate = duplicate.exclude(pk=instance.pk)
        if duplicate.exists():
            raise serializers.ValidationError(
                {
                    "non_field_errors": [
                        "This client is already subscribed to this service."
                    ]
                }
            )
        return attrs


class TaskTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = TaskTemplate
        fields = "__all__"
        read_only_fields = _AUDIT
        # Validate explicitly because tenant_id is injected by the viewset only
        # after serializer validation.
        validators = []

    def validate(self, attrs):
        instance = getattr(self, "instance", None)
        service_id = attrs.get(
            "service_id", getattr(instance, "service_id", None) if instance else None
        )
        name = attrs.get("name", getattr(instance, "name", "") if instance else "")
        normalised_name = (name or "").strip()
        attrs["name"] = normalised_name

        duplicate = TaskTemplate.objects.filter(
            tenant_id=_tenant_id(self),
            service_id=service_id,
            name=normalised_name,
        )
        if instance is not None:
            duplicate = duplicate.exclude(pk=instance.pk)
        if duplicate.exists():
            raise serializers.ValidationError(
                {
                    "name": (
                        "A task template with this name already exists for "
                        "the selected service."
                    )
                }
            )
        return attrs


class RecurringWorkProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = RecurringWorkProfile
        fields = "__all__"
        read_only_fields = _AUDIT


class GeneratedWorkLedgerSerializer(serializers.ModelSerializer):
    class Meta:
        model = GeneratedWorkLedger
        fields = "__all__"
        read_only_fields = _AUDIT
