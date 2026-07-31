from __future__ import annotations

from rest_framework import serializers

from .models import AuditEvent


class AuditEventSerializer(serializers.ModelSerializer):
    action_label = serializers.SerializerMethodField()

    class Meta:
        model = AuditEvent
        fields = "__all__"
        read_only_fields = tuple(f.name for f in AuditEvent._meta.fields)

    @staticmethod
    def get_action_label(obj):
        return obj.get_action_display()
