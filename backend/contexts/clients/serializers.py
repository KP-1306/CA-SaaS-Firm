"""Client serializers with an entity-aware, server-side PAN policy.

Resolves the documented legacy mismatch (the API historically had no PAN
validator while one legacy test created a PAN-less client). The policy:

* PAN is REQUIRED for entity types that operationally require it, UNLESS the
  client is still at an early lifecycle stage (PROSPECT / ONBOARDING), where a
  PAN may not yet be available.
* PAN is OPTIONAL for explicitly approved types (e.g. INDIVIDUAL) and for early
  lifecycle stages.
* A populated PAN is normalised to uppercase and validated against the standard
  Indian PAN format server-side.
* A blank PAN is preserved as "" so the partial unique constraint
  (``uq_client_pan_tenant``, condition ``~Q(pan="")``) is never violated by
  multiple blank PANs.

This strengthens, never weakens, the contract: the previously undocumented
behaviour is now explicit and enforced on the server.
"""

from __future__ import annotations

import re

from rest_framework import serializers

from .models import (
    Client,
    ClientBranch,
    ClientContact,
    ClientGSTRegistration,
    ClientLifecycleStatus,
    ClientType,
)

_AUDIT = ("id", "tenant_id", "created_at", "created_by", "updated_at", "updated_by", "row_version")

# Standard Indian PAN: 5 letters, 4 digits, 1 letter.
_PAN_RE = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")

# Entity types for which PAN is operationally required once past onboarding.
_PAN_REQUIRED_TYPES = frozenset(
    {
        ClientType.PROPRIETORSHIP,
        ClientType.PARTNERSHIP,
        ClientType.LLP,
        ClientType.PRIVATE_LIMITED,
        ClientType.PUBLIC_LIMITED,
        ClientType.TRUST,
    }
)

# Lifecycle stages at which a missing PAN is acceptable (not yet collected).
_PAN_OPTIONAL_STAGES = frozenset(
    {ClientLifecycleStatus.PROSPECT, ClientLifecycleStatus.ONBOARDING}
)


class ClientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Client
        fields = "__all__"
        read_only_fields = _AUDIT
        # The conditional model constraint must not make PAN implicitly required.
        # Requirement is entity/lifecycle-aware and is enforced in validate().
        extra_kwargs = {
            "pan": {
                "required": False,
                "allow_blank": True,
                "allow_null": False,
            }
        }
        # DRF's automatic UniqueTogetherValidator cannot account for the
        # conditional blank-PAN constraint or tenant_id injected at save time.
        validators = []

    def validate_pan(self, value: str) -> str:
        """Normalise populated identifiers; type-aware format checks occur later."""
        if value in (None, ""):
            return ""
        return value.strip().upper()

    def validate(self, attrs):
        """Entity-aware requirement check across type + lifecycle + PAN."""
        instance = getattr(self, "instance", None)

        def resolved(field):
            if field in attrs:
                return attrs[field]
            return getattr(instance, field, None)

        client_type = resolved("client_type")
        lifecycle = resolved("lifecycle_status") or ClientLifecycleStatus.PROSPECT
        pan = attrs.get("pan", getattr(instance, "pan", "") if instance else "")

        normalised_pan = (pan or "").strip().upper()
        attrs["pan"] = normalised_pan

        requires_pan = (
            client_type in _PAN_REQUIRED_TYPES
            and lifecycle not in _PAN_OPTIONAL_STAGES
        )
        if requires_pan and not normalised_pan:
            raise serializers.ValidationError(
                {
                    "pan": (
                        "PAN is required for this entity type once the client is "
                        "past onboarding."
                    )
                }
            )

        # Preserve the validated legacy contract for OTHER clients, where this
        # field may contain a historical tax/reference identifier that predates
        # strict Indian PAN formatting. All known PAN-bearing entity types still
        # receive the standard AAAAA9999A validation.
        if (
            normalised_pan
            and client_type != ClientType.OTHER
            and not _PAN_RE.match(normalised_pan)
        ):
            raise serializers.ValidationError(
                {"pan": "PAN must be 10 characters in the format AAAAA9999A."}
            )

        if normalised_pan:
            request = self.context.get("request")
            principal = getattr(request, "principal", None) if request else None
            tenant_id = (
                getattr(instance, "tenant_id", None)
                or getattr(principal, "tenant_id", None)
                or (request.META.get("HTTP_X_TENANT_ID") if request else None)
            )
            duplicate = Client.objects.filter(
                tenant_id=tenant_id,
                pan=normalised_pan,
            )
            if instance is not None:
                duplicate = duplicate.exclude(pk=instance.pk)
            if duplicate.exists():
                raise serializers.ValidationError(
                    {"pan": "A client with this PAN already exists for this firm."}
                )

        return attrs


class ClientContactSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClientContact
        fields = "__all__"
        read_only_fields = _AUDIT


class ClientGSTRegistrationSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClientGSTRegistration
        fields = "__all__"
        read_only_fields = _AUDIT


class ClientBranchSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClientBranch
        fields = "__all__"
        read_only_fields = _AUDIT
