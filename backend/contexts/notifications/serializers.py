from __future__ import annotations

from rest_framework import serializers

from .models import Notification


class NotificationSerializer(
    serializers.ModelSerializer
):
    class Meta:
        model = Notification
        fields = [
            "id",
            "notification_type",
            "title",
            "message",
            "entity_type",
            "entity_id",
            "read_at",
            "metadata",
            "created_at",
        ]
        read_only_fields = fields
