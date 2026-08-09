"""Serializers for the generation context.

Follows the platform convention exactly: ``ModelSerializer`` with
``fields="__all__"`` and the 7 audit fields read-only. No raw-UUID text inputs
are introduced on the frontend; UUID references are selected via existing
pickers, matching the client/work screens.
"""

from __future__ import annotations

from rest_framework import serializers

from contexts.configuration.models import ServiceOperationalField

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

    def validate(self, attrs):
        instance = getattr(self, "instance", None)

        tenant_id = _tenant_id(self)

        subscription_id = attrs.get(
            "subscription_id",
            getattr(instance, "subscription_id", None),
        )

        client_id = attrs.get(
            "client_id",
            getattr(instance, "client_id", None),
        )

        service_id = attrs.get(
            "service_id",
            getattr(instance, "service_id", None),
        )

        subscription = ClientServiceSubscription.objects.filter(
            tenant_id=tenant_id,
            id=subscription_id,
        ).first()

        if subscription is None:
            raise serializers.ValidationError(
                {
                    "subscription_id": (
                        "Select a valid client service subscription."
                    )
                }
            )

        if subscription.client_id != client_id:
            raise serializers.ValidationError(
                {
                    "client_id": (
                        "Client must match the selected subscription."
                    )
                }
            )

        if subscription.service_id != service_id:
            raise serializers.ValidationError(
                {
                    "service_id": (
                        "Service must match the selected subscription."
                    )
                }
            )

        operational_defaults = attrs.get(
            "operational_defaults",
            getattr(
                instance,
                "operational_defaults",
                {},
            ),
        )

        attrs["operational_defaults"] = (
            self._validate_operational_defaults(
                tenant_id=tenant_id,
                service_id=service_id,
                values=operational_defaults,
            )
        )

        return attrs

    def _validate_operational_defaults(
        self,
        *,
        tenant_id,
        service_id,
        values,
    ):
        if values in (None, ""):
            values = {}

        if not isinstance(values, dict):
            raise serializers.ValidationError(
                {
                    "operational_defaults": (
                        "Operational defaults must be supplied as an object."
                    )
                }
            )

        definitions = list(
            ServiceOperationalField.objects.filter(
                tenant_id=tenant_id,
                service_id=service_id,
                is_active=True,
            ).order_by(
                "display_order",
                "label",
                "id",
            )
        )

        definition_map = {
            field.key: field
            for field in definitions
        }

        unknown = sorted(
            set(values) - set(definition_map)
        )

        if unknown:
            raise serializers.ValidationError(
                {
                    "operational_defaults": (
                        "Unknown operational field(s): "
                        + ", ".join(unknown)
                    )
                }
            )

        cleaned = {}

        for field in definitions:
            supplied = field.key in values
            value = values.get(field.key)

            if value is None:
                value = ""

            # Recurring-profile operational defaults are intentionally
            # partial. Required service fields may be period/work-instance
            # values (for example financial year or quarter), so absence here
            # is valid. Any value that IS supplied is still validated against
            # the service catalogue below.
            if not supplied or value == "":
                continue

            if field.field_type in (
                "TEXT",
                "LONG_TEXT",
            ):
                cleaned[field.key] = str(
                    value
                ).strip()

            elif field.field_type == "NUMBER":
                if isinstance(value, bool):
                    raise serializers.ValidationError(
                        {
                            "operational_defaults": {
                                field.key: (
                                    f"{field.label} must be a number."
                                )
                            }
                        }
                    )

                try:
                    cleaned[field.key] = float(
                        value
                    )
                except (TypeError, ValueError):
                    raise serializers.ValidationError(
                        {
                            "operational_defaults": {
                                field.key: (
                                    f"{field.label} must be a number."
                                )
                            }
                        }
                    )

            elif field.field_type == "BOOLEAN":
                if not isinstance(value, bool):
                    raise serializers.ValidationError(
                        {
                            "operational_defaults": {
                                field.key: (
                                    f"{field.label} must be Yes or No."
                                )
                            }
                        }
                    )

                cleaned[field.key] = value

            elif field.field_type == "DATE":
                date_field = serializers.DateField()

                try:
                    cleaned[field.key] = (
                        date_field
                        .to_internal_value(value)
                        .isoformat()
                    )
                except serializers.ValidationError:
                    raise serializers.ValidationError(
                        {
                            "operational_defaults": {
                                field.key: (
                                    f"{field.label} must be a valid date."
                                )
                            }
                        }
                    )

            elif field.field_type == "SELECT":
                value_text = str(value).strip()

                if value_text not in field.options:
                    raise serializers.ValidationError(
                        {
                            "operational_defaults": {
                                field.key: (
                                    "Select a valid value for "
                                    f"{field.label}."
                                )
                            }
                        }
                    )

                cleaned[field.key] = value_text

        return cleaned


class GeneratedWorkLedgerSerializer(serializers.ModelSerializer):
    class Meta:
        model = GeneratedWorkLedger
        fields = "__all__"
        read_only_fields = _AUDIT
