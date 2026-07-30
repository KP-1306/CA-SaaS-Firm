from __future__ import annotations

from rest_framework import serializers

from .models import FirmProfile, Branch, Team


class FirmProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = FirmProfile
        fields = "__all__"
        read_only_fields = ("id", "tenant_id", "created_at", "created_by", "updated_at", "updated_by", "row_version")

class BranchSerializer(serializers.ModelSerializer):
    class Meta:
        model = Branch
        fields = "__all__"
        read_only_fields = ("id", "tenant_id", "created_at", "created_by", "updated_at", "updated_by", "row_version")

class TeamSerializer(serializers.ModelSerializer):
    class Meta:
        model = Team
        fields = "__all__"
        read_only_fields = ("id", "tenant_id", "created_at", "created_by", "updated_at", "updated_by", "row_version")
