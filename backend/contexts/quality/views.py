from __future__ import annotations

from rest_framework.exceptions import PermissionDenied

from core.api.viewsets import TenantModelViewSet

from .models import (
    QAReviewCycle,
    QAReviewIssue,
    QAReviewResponse,
    ServiceQAChecklistItem,
    ServiceQAChecklistSet,
)
from .serializers import (
    QAReviewCycleSerializer,
    QAReviewIssueSerializer,
    QAReviewResponseSerializer,
    ServiceQAChecklistItemSerializer,
    ServiceQAChecklistSetSerializer,
)


class ServiceQAChecklistSetViewSet(TenantModelViewSet):
    queryset = ServiceQAChecklistSet.objects.all()
    serializer_class = ServiceQAChecklistSetSerializer
    search_fields = ["name", "description"]

    def get_queryset(self):
        qs = super().get_queryset()
        for field in ("service_id", "status", "version_number"):
            value = self.request.query_params.get(field)
            if value not in (None, ""):
                qs = qs.filter(**{field: value})
        return qs


class ServiceQAChecklistItemViewSet(TenantModelViewSet):
    queryset = ServiceQAChecklistItem.objects.all()
    serializer_class = ServiceQAChecklistItemSerializer
    search_fields = ["code", "title", "description", "guidance"]

    def get_queryset(self):
        qs = super().get_queryset()
        for field in ("checklist_set_id", "service_id", "mandatory", "is_active"):
            value = self.request.query_params.get(field)
            if value not in (None, ""):
                qs = qs.filter(**{field: value})
        return qs


class _ReadOnlyQualityEvidenceViewSet(TenantModelViewSet):
    http_method_names = ["get", "head", "options"]

    def create(self, request, *args, **kwargs):
        raise PermissionDenied(
            "QA operational evidence is created only through approved workflow actions."
        )

    def update(self, request, *args, **kwargs):
        raise PermissionDenied("QA operational evidence cannot be edited directly.")

    def partial_update(self, request, *args, **kwargs):
        raise PermissionDenied("QA operational evidence cannot be edited directly.")

    def destroy(self, request, *args, **kwargs):
        raise PermissionDenied("QA operational evidence cannot be deleted.")


class QAReviewCycleViewSet(_ReadOnlyQualityEvidenceViewSet):
    queryset = QAReviewCycle.objects.all()
    serializer_class = QAReviewCycleSerializer


class QAReviewResponseViewSet(_ReadOnlyQualityEvidenceViewSet):
    queryset = QAReviewResponse.objects.all()
    serializer_class = QAReviewResponseSerializer


class QAReviewIssueViewSet(_ReadOnlyQualityEvidenceViewSet):
    queryset = QAReviewIssue.objects.all()
    serializer_class = QAReviewIssueSerializer
