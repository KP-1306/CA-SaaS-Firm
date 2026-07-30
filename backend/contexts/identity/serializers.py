from __future__ import annotations

from rest_framework import serializers

from .models import Employee


class EmployeeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Employee
        fields = "__all__"
        read_only_fields = ("id", "tenant_id", "created_at", "created_by", "updated_at", "updated_by", "row_version")
