from django.db import models

from core.api.viewsets import TenantModelViewSet
from .models import (
    Domain,
    Service,
    ServiceDocumentRequirement,
    ServiceDocumentRequirementSet,
    Vertical,
    ServiceOperationalField,
)
from .serializers import (
    DomainSerializer,
    ServiceDocumentRequirementSerializer,
    ServiceDocumentRequirementSetSerializer,
    ServiceSerializer,
    VerticalSerializer,
    ServiceOperationalFieldSerializer,
)

class VerticalViewSet(TenantModelViewSet):
    queryset = Vertical.objects.all(); serializer_class = VerticalSerializer; search_fields = ["name", "code", "description"]
class DomainViewSet(TenantModelViewSet):
    queryset = Domain.objects.all(); serializer_class = DomainSerializer; search_fields = ["name", "code", "description"]
    def get_queryset(self):
        qs=super().get_queryset(); value=self.request.query_params.get("vertical_id"); return qs.filter(vertical_id=value) if value else qs
class ServiceViewSet(TenantModelViewSet):
    queryset = Service.objects.all(); serializer_class = ServiceSerializer; search_fields = ["name", "code", "description"]
    def get_queryset(self):
        qs=super().get_queryset(); value=self.request.query_params.get("domain_id"); return qs.filter(domain_id=value) if value else qs


class ServiceDocumentRequirementSetViewSet(
    TenantModelViewSet
):
    queryset = ServiceDocumentRequirementSet.objects.all()
    serializer_class = ServiceDocumentRequirementSetSerializer

    search_fields = [
        "name",
        "description",
    ]

    ordering_fields = [
        "version_number",
        "effective_from",
        "effective_until",
        "status",
        "created_at",
    ]

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params

        for field in (
            "service_id",
            "status",
            "version_number",
        ):
            value = params.get(field)

            if value not in (None, ""):
                qs = qs.filter(**{field: value})

        active_on = params.get("active_on")

        if active_on:
            qs = qs.filter(
                effective_from__lte=active_on,
            ).filter(
                models.Q(effective_until__isnull=True)
                | models.Q(effective_until__gte=active_on)
            )

        return qs


class ServiceDocumentRequirementViewSet(
    TenantModelViewSet
):
    queryset = ServiceDocumentRequirement.objects.all()
    serializer_class = ServiceDocumentRequirementSerializer

    search_fields = [
        "name",
        "code",
        "description",
        "allowed_extensions",
    ]

    ordering_fields = [
        "display_order",
        "name",
        "category",
        "mandatory",
        "created_at",
    ]

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params

        for field in (
            "requirement_set_id",
            "service_id",
            "category",
            "mandatory",
            "is_active",
        ):
            value = params.get(field)

            if value not in (None, ""):
                qs = qs.filter(**{field: value})

        return qs


class ServiceOperationalFieldViewSet(TenantModelViewSet):
    queryset = ServiceOperationalField.objects.all()
    serializer_class = ServiceOperationalFieldSerializer

    search_fields = [
        "key",
        "label",
        "help_text",
        "placeholder",
    ]

    ordering_fields = [
        "display_order",
        "label",
        "field_type",
        "required",
        "created_at",
    ]

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params

        for field in (
            "service_id",
            "field_type",
            "required",
            "is_active",
        ):
            value = params.get(field)

            if value not in (None, ""):
                qs = qs.filter(**{field: value})

        return qs
