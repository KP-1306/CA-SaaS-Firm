from __future__ import annotations

from rest_framework import serializers

from .models import AssignmentDecision, AssignmentEvent, ReviewerRule

_AUDIT = ("id", "tenant_id", "created_at", "created_by", "updated_at", "updated_by", "row_version")


class ReviewerRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReviewerRule
        fields = "__all__"
        read_only_fields = _AUDIT


class AssignmentDecisionSerializer(serializers.ModelSerializer):
    class Meta:
        model = AssignmentDecision
        fields = "__all__"
        read_only_fields = _AUDIT


class AssignmentEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = AssignmentEvent
        fields = "__all__"
        read_only_fields = _AUDIT
