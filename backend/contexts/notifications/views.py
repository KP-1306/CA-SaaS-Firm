from __future__ import annotations

from django.utils import timezone

from rest_framework import (
    mixins,
    status,
    viewsets,
)
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.api.request_context import (
    HeaderPrincipalAuthentication,
    InternalPrincipal,
)

from .models import Notification
from .serializers import NotificationSerializer


class NotificationViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    authentication_classes = [
        HeaderPrincipalAuthentication
    ]
    permission_classes = [IsAuthenticated]
    serializer_class = NotificationSerializer

    def principal(self) -> InternalPrincipal:
        return self.request.user

    def get_queryset(self):
        principal = self.principal()

        qs = Notification.objects.filter(
            tenant_id=principal.tenant_id,
            recipient_principal_id=(
                principal.principal_id
            ),
        )

        unread = self.request.query_params.get(
            "unread"
        )

        if unread == "true":
            qs = qs.filter(read_at__isnull=True)
        elif unread == "false":
            qs = qs.filter(read_at__isnull=False)

        return qs

    @action(
        detail=True,
        methods=["post"],
        url_path="read",
    )
    def mark_read(self, request, pk=None):
        notification = self.get_object()

        if notification.read_at is None:
            notification.read_at = timezone.now()
            notification.updated_by = (
                self.principal().principal_id
            )
            notification.save(
                update_fields=[
                    "read_at",
                    "updated_by",
                    "updated_at",
                ]
            )

        return Response(
            self.get_serializer(
                notification
            ).data,
            status=status.HTTP_200_OK,
        )
