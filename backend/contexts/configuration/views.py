from django.db import models

from core.api.viewsets import TenantModelViewSet
from .models import (
    Domain,
    Service,
    ServiceDocumentRequirement,
    ServiceDocumentRequirementSet,
    Vertical,
    ServiceProcessStep,
    ServiceOperationalField,
)
from .serializers import (
    DomainSerializer,
    ServiceDocumentRequirementSerializer,
    ServiceDocumentRequirementSetSerializer,
    ServiceSerializer,
    VerticalSerializer,
    ServiceProcessStepSerializer,
    ServiceOperationalFieldSerializer,
)



def _query_bool(value):
    """
    Convert an HTTP query-string boolean to a Python bool.

    Returns None when the value is absent/blank.
    Raises ValueError for unsupported values so callers can
    avoid silently applying an incorrect filter.
    """
    if value in (None, ""):
        return None

    normalized = str(value).strip().lower()

    if normalized in {"true", "1"}:
        return True

    if normalized in {"false", "0"}:
        return False

    raise ValueError(
        "Boolean query parameter must be true, false, 1, or 0."
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
        ):
            value = params.get(field)

            if value not in (None, ""):
                qs = qs.filter(**{field: value})

        for field in (
            "mandatory",
            "is_active",
        ):
            value = _query_bool(params.get(field))

            if value is not None:
                qs = qs.filter(**{field: value})

        return qs


class ServiceProcessStepViewSet(TenantModelViewSet):
    serializer_class = ServiceProcessStepSerializer

    queryset = ServiceProcessStep.objects.all()

    def get_queryset(self):
        qs = super().get_queryset().order_by(
            "service_id",
            "display_order",
            "name",
            "id",
        )

        params = self.request.query_params

        service_id = params.get("service_id")
        if service_id not in (None, ""):
            qs = qs.filter(service_id=service_id)

        is_active = _query_bool(params.get("is_active"))
        if is_active is not None:
            qs = qs.filter(is_active=is_active)

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
        ):
            value = params.get(field)

            if value not in (None, ""):
                qs = qs.filter(**{field: value})

        for field in (
            "required",
            "is_active",
        ):
            value = _query_bool(params.get(field))

            if value is not None:
                qs = qs.filter(**{field: value})

        return qs
