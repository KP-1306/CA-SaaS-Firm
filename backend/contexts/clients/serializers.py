from __future__ import annotations

from rest_framework import serializers

from .models import Client, ClientBranch, ClientContact, ClientGSTRegistration

_AUDIT = ("id", "tenant_id", "created_at", "created_by", "updated_at", "updated_by", "row_version")


class ClientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Client
        fields = "__all__"
        read_only_fields = _AUDIT


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
