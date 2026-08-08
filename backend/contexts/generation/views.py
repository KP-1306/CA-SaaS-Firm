"""Viewsets for the generation context.

All viewsets subclass ``TenantModelViewSet`` (tenant-scoped) and expose
query-param filters in ``get_queryset``, matching the work/clients viewsets. The
``generate`` action on recurring profiles wires the idempotent generator with
fail-closed mandatory audit, exactly like the work viewset's transitions.
"""

from __future__ import annotations

import datetime as _dt

from django.db import transaction
from rest_framework.decorators import action
from rest_framework.exceptions import APIException
from rest_framework.response import Response

from core.api.viewsets import TenantModelViewSet
from contexts.audit.models import AuditAction
from contexts.audit.recording import record_event

from .generation import (
    generate_for_profile,
    preview_for_profile,
)
from .models import (
    ClientServiceSubscription,
    GeneratedWorkLedger,
    RecurringWorkProfile,
    TaskTemplate,
)
from .serializers import (
    ClientServiceSubscriptionSerializer,
    GeneratedWorkLedgerSerializer,
    RecurringWorkProfileSerializer,
    TaskTemplateSerializer,
)


class MandatoryAuditPersistenceError(APIException):
    """Fail closed when a mandatory audit event cannot be persisted."""

    status_code = 503
    default_detail = (
        "The requested change was not saved because the mandatory audit record "
        "could not be persisted. Please retry later."
    )
    default_code = "mandatory_audit_unavailable"


class ClientServiceSubscriptionViewSet(TenantModelViewSet):
    queryset = ClientServiceSubscription.objects.all()
    serializer_class = ClientServiceSubscriptionSerializer
    search_fields = ["notes"]
    ordering_fields = ["created_at", "status", "frequency"]

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        for field in ("client_id", "service_id", "status", "frequency"):
            value = params.get(field)
            if value:
                qs = qs.filter(**{field: value})
        return qs


class TaskTemplateViewSet(TenantModelViewSet):
    queryset = TaskTemplate.objects.all()
    serializer_class = TaskTemplateSerializer
    search_fields = ["name", "description", "default_title"]
    ordering_fields = ["name", "created_at"]

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        for field in ("service_id", "is_active"):
            value = params.get(field)
            if value not in (None, ""):
                qs = qs.filter(**{field: value})
        return qs


class GeneratedWorkLedgerViewSet(TenantModelViewSet):
    queryset = GeneratedWorkLedger.objects.all()
    serializer_class = GeneratedWorkLedgerSerializer
    http_method_names = ["get", "head", "options"]

    def get_queryset(self):
        qs = super().get_queryset()
        value = self.request.query_params.get("recurring_profile_id")
        return qs.filter(recurring_profile_id=value) if value else qs


class RecurringWorkProfileViewSet(TenantModelViewSet):
    queryset = RecurringWorkProfile.objects.all()
    serializer_class = RecurringWorkProfileSerializer
    ordering_fields = ["created_at", "frequency"]

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        for field in ("subscription_id", "client_id", "service_id", "is_active"):
            value = params.get(field)
            if value not in (None, ""):
                qs = qs.filter(**{field: value})
        return qs

    def _requested_date(self, request):
        raw_date = request.data.get("on_date")

        if not raw_date:
            return _dt.date.today()

        try:
            return _dt.date.fromisoformat(
                str(raw_date),
            )
        except ValueError:
            return None

    def _selected_profiles(self, request):
        profile_ids = request.data.get(
            "profile_ids",
            [],
        )

        qs = self.get_queryset().filter(
            is_active=True,
        )

        if profile_ids:
            qs = qs.filter(id__in=profile_ids)

        return list(qs)

    @action(
        detail=False,
        methods=["post"],
        url_path="preview-batch",
    )
    def preview_batch(self, request):
        on_date = self._requested_date(request)

        if on_date is None:
            return Response(
                {
                    "detail": (
                        "on_date must be an ISO date "
                        "(YYYY-MM-DD)."
                    )
                },
                status=400,
            )

        profiles = self._selected_profiles(request)

        previews = [
            preview_for_profile(
                profile,
                on_date=on_date,
            ).__dict__
            for profile in profiles
        ]

        return Response(
            {
                "on_date": on_date.isoformat(),
                "total": len(previews),
                "ready": sum(
                    1
                    for item in previews
                    if item["eligible"]
                ),
                "already_generated": sum(
                    1
                    for item in previews
                    if item[
                        "already_generated"
                    ]
                ),
                "blocked": sum(
                    1
                    for item in previews
                    if (
                        not item["eligible"]
                        and not item[
                            "already_generated"
                        ]
                    )
                ),
                "items": previews,
            }
        )

    @action(
        detail=False,
        methods=["post"],
        url_path="generate-batch",
    )
    def generate_batch(self, request):
        if request.data.get("approved") is not True:
            return Response(
                {
                    "detail": (
                        "Explicit human approval is "
                        "required before generation."
                    )
                },
                status=400,
            )

        on_date = self._requested_date(request)

        if on_date is None:
            return Response(
                {
                    "detail": (
                        "on_date must be an ISO date "
                        "(YYYY-MM-DD)."
                    )
                },
                status=400,
            )

        principal = self.principal()
        profiles = self._selected_profiles(request)

        results = []

        for profile in profiles:
            preview = preview_for_profile(
                profile,
                on_date=on_date,
            )

            if preview.already_generated:
                results.append(
                    {
                        "profile_id": str(
                            profile.id
                        ),
                        "status": (
                            "ALREADY_GENERATED"
                        ),
                        "period_key": (
                            preview.period_key
                        ),
                        "work_item_id": (
                            preview.work_item_id
                        ),
                    }
                )
                continue

            if not preview.eligible:
                results.append(
                    {
                        "profile_id": str(
                            profile.id
                        ),
                        "status": "BLOCKED",
                        "period_key": (
                            preview.period_key
                        ),
                        "reason": preview.reason,
                    }
                )
                continue

            with transaction.atomic():
                result = generate_for_profile(
                    profile,
                    on_date=on_date,
                    principal_id=(
                        principal.principal_id
                    ),
                    enforce_eligibility=True,
                )

                if result.created:
                    record_event(
                        tenant_id=profile.tenant_id,
                        principal_id=(
                            principal.principal_id
                        ),
                        action=AuditAction.CREATE,
                        entity_type="WorkItem",
                        entity_id=result.work_item_id,
                        summary=(
                            "Generated recurring work "
                            f"for period "
                            f"{result.period_key}"
                        ),
                        new={
                            "period": (
                                result.period_key
                            ),
                            "recurring_profile_id": (
                                str(profile.id)
                            ),
                            "generation_mode": (
                                "APPROVED_BATCH"
                            ),
                        },
                        request=self.request,
                    )

            results.append(
                {
                    "profile_id": str(
                        profile.id
                    ),
                    "status": (
                        "CREATED"
                        if result.created
                        else "ALREADY_GENERATED"
                    ),
                    "period_key": (
                        result.period_key
                    ),
                    "work_item_id": (
                        str(result.work_item_id)
                        if result.work_item_id
                        else None
                    ),
                }
            )

        return Response(
            {
                "on_date": on_date.isoformat(),
                "total": len(results),
                "created": sum(
                    1
                    for item in results
                    if item["status"]
                    == "CREATED"
                ),
                "already_generated": sum(
                    1
                    for item in results
                    if item["status"]
                    == "ALREADY_GENERATED"
                ),
                "blocked": sum(
                    1
                    for item in results
                    if item["status"]
                    == "BLOCKED"
                ),
                "items": results,
            }
        )
    @action(detail=True, methods=["post"])
    def generate(self, request, pk=None):
        """Idempotently generate the work item for a given (or today's) period.

        Body: optional ``on_date`` (ISO date; defaults to today) and optional
        ``title``. Mandatory audit is written in the same transaction as the
        generation; an audit failure rolls the generation back (fail-closed).
        """
        profile = self.get_object()
        principal = self.principal()
        raw_date = request.data.get("on_date")
        if raw_date:
            try:
                on_date = _dt.date.fromisoformat(str(raw_date))
            except ValueError:
                return Response({"detail": "on_date must be an ISO date (YYYY-MM-DD)."}, status=400)
        else:
            on_date = _dt.date.today()

        try:
            with transaction.atomic():
                result = generate_for_profile(
                    profile,
                    on_date=on_date,
                    principal_id=principal.principal_id,
                    title=request.data.get("title"),
                    enforce_eligibility=True,
                )
                if result.created:
                    record_event(
                        tenant_id=profile.tenant_id,
                        principal_id=principal.principal_id,
                        action=AuditAction.CREATE,
                        entity_type="WorkItem",
                        entity_id=result.work_item_id,
                        summary=f"Generated for period {result.period_key}",
                        new={"period": result.period_key, "recurring_profile_id": str(profile.id)},
                        request=self.request,
                    )
        except MandatoryAuditPersistenceError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise MandatoryAuditPersistenceError() from exc

        return Response(
            {
                "created": result.created,
                "already_generated": result.already_generated,
                "period_key": result.period_key,
                "work_item_id": str(result.work_item_id) if result.work_item_id else None,
            },
            status=201 if result.created else 200,
        )
