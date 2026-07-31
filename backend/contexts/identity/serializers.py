from __future__ import annotations

from rest_framework import serializers

from .models import Employee, EmployeeExpertise

_AUDIT = ("id", "tenant_id", "created_at", "created_by", "updated_at", "updated_by", "row_version")


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

    def get_expertise_records(self, obj):
        records = EmployeeExpertise.objects.filter(tenant_id=obj.tenant_id, employee_id=obj.id)
        return EmployeeExpertiseSerializer(records, many=True).data
