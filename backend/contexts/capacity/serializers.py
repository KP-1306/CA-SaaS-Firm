from __future__ import annotations

from rest_framework import serializers

from .models import (
    CapacityOverride,
    CapacityProfile,
    CapacityReservation,
    Holiday,
    LeaveRecord,
    LeaveType,
)

_AUDIT = ("id", "tenant_id", "created_at", "created_by", "updated_at", "updated_by", "row_version")


class CapacityProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = CapacityProfile
        fields = "__all__"
        read_only_fields = _AUDIT


class CapacityOverrideSerializer(serializers.ModelSerializer):
    class Meta:
        model = CapacityOverride
        fields = "__all__"
        read_only_fields = _AUDIT


class CapacityReservationSerializer(serializers.ModelSerializer):
    class Meta:
        model = CapacityReservation
        fields = "__all__"
        read_only_fields = _AUDIT


class LeaveTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeaveType
        fields = "__all__"
        read_only_fields = _AUDIT


class LeaveRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeaveRecord
        fields = "__all__"
        read_only_fields = _AUDIT + ("status", "approved_by", "decided_at", "decision_comment")

    def validate(self, attrs):
        instance = getattr(self, "instance", None)
        start = attrs.get("start_date", getattr(instance, "start_date", None))
        end = attrs.get("end_date", getattr(instance, "end_date", None))
        if start and end and end < start:
            raise serializers.ValidationError({"end_date": "End date cannot be before start date."})
        if attrs.get("is_partial_day") and attrs.get("hours") in (None, ""):
            raise serializers.ValidationError({"hours": "Partial-day leave requires hours."})
        return attrs


class HolidaySerializer(serializers.ModelSerializer):
    class Meta:
        model = Holiday
        fields = "__all__"
        read_only_fields = _AUDIT
