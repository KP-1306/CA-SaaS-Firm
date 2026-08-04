from __future__ import annotations

from rest_framework import serializers

from .models import (
    QAReviewCycle,
    QAReviewIssue,
    QAReviewResponse,
    ServiceQAChecklistItem,
    ServiceQAChecklistSet,
)

_AUDIT_FIELDS = (
    "id",
    "tenant_id",
    "created_at",
    "created_by",
    "updated_at",
    "updated_by",
    "row_version",
)


class ServiceQAChecklistSetSerializer(serializers.ModelSerializer):
    item_count = serializers.SerializerMethodField()
    mandatory_item_count = serializers.SerializerMethodField()

    class Meta:
        model = ServiceQAChecklistSet
        fields = "__all__"
        read_only_fields = _AUDIT_FIELDS
        validators = []

    @staticmethod
    def get_item_count(obj):
        return ServiceQAChecklistItem.objects.filter(
            tenant_id=obj.tenant_id,
            checklist_set_id=obj.id,
            is_active=True,
        ).count()

    @staticmethod
    def get_mandatory_item_count(obj):
        return ServiceQAChecklistItem.objects.filter(
            tenant_id=obj.tenant_id,
            checklist_set_id=obj.id,
            is_active=True,
            mandatory=True,
        ).count()


class ServiceQAChecklistItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceQAChecklistItem
        fields = "__all__"
        read_only_fields = _AUDIT_FIELDS
        validators = []


class QAReviewCycleSerializer(serializers.ModelSerializer):
    class Meta:
        model = QAReviewCycle
        fields = "__all__"
        read_only_fields = _AUDIT_FIELDS


class QAReviewResponseSerializer(serializers.ModelSerializer):
    class Meta:
        model = QAReviewResponse
        fields = "__all__"
        read_only_fields = _AUDIT_FIELDS


class QAReviewIssueSerializer(serializers.ModelSerializer):
    class Meta:
        model = QAReviewIssue
        fields = "__all__"
        read_only_fields = _AUDIT_FIELDS
