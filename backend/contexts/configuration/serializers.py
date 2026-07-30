from __future__ import annotations

from rest_framework import serializers

from .models import Vertical, Domain, Service


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
