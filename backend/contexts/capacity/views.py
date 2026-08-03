from __future__ import annotations

import datetime as _dt

from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.decorators import action
from rest_framework.exceptions import APIException, PermissionDenied, ValidationError
from rest_framework.response import Response

from core.api.viewsets import TenantModelViewSet
from contexts.audit.models import AuditAction
from contexts.audit.recording import record_event
from contexts.audit.viewset_mixins import AuditedTenantViewSetMixin
from contexts.identity.access import is_executive

from . import service
from .models import (
    CapacityOverride,
    CapacityProfile,
    CapacityReservation,
    Holiday,
    LeaveRecord,
    LeaveStatus,
    LeaveType,
)
from .serializers import (
    CapacityOverrideSerializer,
    CapacityProfileSerializer,
    CapacityReservationSerializer,
    HolidaySerializer,
    LeaveRecordSerializer,
    LeaveTypeSerializer,
)


class MandatoryAuditPersistenceError(APIException):
    status_code = 503
    default_detail = "The change was not saved because the mandatory audit record could not be persisted."
    default_code = "mandatory_audit_unavailable"


class CapacityProfileViewSet(AuditedTenantViewSetMixin, TenantModelViewSet):
    queryset = CapacityProfile.objects.all()
    serializer_class = CapacityProfileSerializer
    audit_entity_type = "CapacityProfile"
    audit_summary_fields = ("employee_id", "daily_hours", "is_active")
    audit_create_action = AuditAction.CAPACITY_CHANGED
    audit_update_action = AuditAction.CAPACITY_CHANGED

    def get_queryset(self):
        qs = super().get_queryset()
        employee_id = self.request.query_params.get("employee_id")
        return qs.filter(employee_id=employee_id) if employee_id else qs

    @action(detail=False, methods=["get"])
    def summary(self, request):
        """Derived capacity summary for an employee over a date range."""
        principal = self.principal()
        employee_id = request.query_params.get("employee_id")
        if not employee_id:
            return Response({"detail": "employee_id is required."}, status=400)
        today = _dt.date.today()
        try:
            start = _dt.date.fromisoformat(request.query_params.get("start", today.isoformat()))
            end = _dt.date.fromisoformat(request.query_params.get("end", (today + _dt.timedelta(days=6)).isoformat()))
        except ValueError:
            return Response({"detail": "start/end must be ISO dates."}, status=400)
        return Response(service.capacity_summary(principal.tenant_id, employee_id, start, end))


class CapacityOverrideViewSet(AuditedTenantViewSetMixin, TenantModelViewSet):
    queryset = CapacityOverride.objects.all()
    serializer_class = CapacityOverrideSerializer
    audit_entity_type = "CapacityOverride"
    audit_summary_fields = ("employee_id", "override_date", "delta_hours")
    audit_create_action = AuditAction.AVAILABILITY_OVERRIDE_CHANGED
    audit_update_action = AuditAction.AVAILABILITY_OVERRIDE_CHANGED

    def get_queryset(self):
        qs = super().get_queryset()
        employee_id = self.request.query_params.get("employee_id")
        return qs.filter(employee_id=employee_id) if employee_id else qs


class CapacityReservationViewSet(AuditedTenantViewSetMixin, TenantModelViewSet):
    queryset = CapacityReservation.objects.all()
    serializer_class = CapacityReservationSerializer
    audit_entity_type = "CapacityReservation"
    audit_summary_fields = ("employee_id", "start_date", "hours")
    audit_create_action = AuditAction.CAPACITY_CHANGED
    audit_update_action = AuditAction.CAPACITY_CHANGED

    def get_queryset(self):
        qs = super().get_queryset()
        employee_id = self.request.query_params.get("employee_id")
        return qs.filter(employee_id=employee_id) if employee_id else qs


class LeaveTypeViewSet(TenantModelViewSet):
    queryset = LeaveType.objects.all()
    serializer_class = LeaveTypeSerializer
    search_fields = ["name", "code"]

    def perform_create(self, serializer):
        principal = self.principal()
        try:
            serializer.save(
                tenant_id=principal.tenant_id,
                created_by=principal.principal_id,
                updated_by=principal.principal_id,
            )
        except IntegrityError as exc:
            raise ValidationError({"code": "A leave type with this code already exists."}) from exc


class HolidayViewSet(AuditedTenantViewSetMixin, TenantModelViewSet):
    queryset = Holiday.objects.all()
    serializer_class = HolidaySerializer
    search_fields = ["name"]
    audit_entity_type = "Holiday"
    audit_summary_fields = ("name", "holiday_date")
    audit_create_action = AuditAction.ORG_STRUCTURE_CHANGED
    audit_update_action = AuditAction.ORG_STRUCTURE_CHANGED

    def get_queryset(self):
        qs = super().get_queryset()
        for field in ("branch_id", "team_id"):
            value = self.request.query_params.get(field)
            if value:
                qs = qs.filter(**{field: value})
        return qs

    def perform_create(self, serializer):
        principal = self.principal()
        try:
            instance = serializer.save(
                tenant_id=principal.tenant_id,
                created_by=principal.principal_id,
                updated_by=principal.principal_id,
            )
        except IntegrityError as exc:
            raise ValidationError(
                {"holiday_date": "A holiday for this scope and date already exists."}
            ) from exc
        self._record_audit(instance, AuditAction.ORG_STRUCTURE_CHANGED, "Holiday created")


def _overlaps(tenant_id, employee_id, start, end, exclude_id=None):
    """True when a non-terminal leave record overlaps [start, end] for the employee."""
    qs = LeaveRecord.objects.filter(
        tenant_id=tenant_id,
        employee_id=employee_id,
        status__in=(LeaveStatus.REQUESTED, LeaveStatus.APPROVED),
        start_date__lte=end,
        end_date__gte=start,
    )
    if exclude_id:
        qs = qs.exclude(id=exclude_id)
    return qs.exists()


class LeaveRecordViewSet(TenantModelViewSet):
    queryset = LeaveRecord.objects.all()
    serializer_class = LeaveRecordSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        for field in ("employee_id", "status"):
            value = self.request.query_params.get(field)
            if value:
                qs = qs.filter(**{field: value})
        return qs

    def perform_create(self, serializer):
        principal = self.principal()
        data = serializer.validated_data
        if _overlaps(principal.tenant_id, data.get("employee_id"), data.get("start_date"), data.get("end_date")):
            raise ValidationError({"start_date": "This overlaps an existing leave request for the employee."})
        with transaction.atomic():
            instance = serializer.save(
                tenant_id=principal.tenant_id,
                created_by=principal.principal_id,
                updated_by=principal.principal_id,
                status=LeaveStatus.REQUESTED,
            )
            self._audit(instance, AuditAction.LEAVE_CREATED, "Leave requested")

    def _audit(self, instance, action_value, summary):
        principal = self.principal()
        try:
            record_event(
                tenant_id=instance.tenant_id,
                principal_id=principal.principal_id,
                action=action_value,
                entity_type="LeaveRecord",
                entity_id=instance.id,
                summary=summary,
                new={"status": instance.status, "employee_id": str(instance.employee_id)},
                request=self.request,
            )
        except Exception as exc:  # noqa: BLE001
            raise MandatoryAuditPersistenceError() from exc

    def _require_approver(self):
        principal = self.principal()
        # Leave approval is a management capability: firm leadership (executive)
        # or an explicit MANAGER role. Fail closed otherwise.
        from contexts.identity.access import caller_role

        if is_executive(principal.tenant_id, principal) or caller_role(principal.tenant_id, principal) == "MANAGER":
            return
        raise PermissionDenied("You are not permitted to decide leave requests.")

    def _decide(self, request, pk, new_status, action_value, verb):
        leave = self.get_object()
        if leave.status != LeaveStatus.REQUESTED:
            return Response({"detail": f"Only requested leave can be {verb}."}, status=400)
        self._require_approver()
        principal = self.principal()
        comment = request.data.get("comment", "")
        with transaction.atomic():
            leave.status = new_status
            leave.approved_by = principal.principal_id
            leave.decided_at = timezone.now()
            leave.decision_comment = comment
            leave.updated_by = principal.principal_id
            leave.save(update_fields=["status", "approved_by", "decided_at", "decision_comment", "updated_by", "row_version"])
            self._audit(leave, action_value, f"Leave {verb}")
        return Response(self.get_serializer(leave).data)

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        return self._decide(request, pk, LeaveStatus.APPROVED, AuditAction.LEAVE_APPROVED, "approved")

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        return self._decide(request, pk, LeaveStatus.REJECTED, AuditAction.LEAVE_REJECTED, "rejected")

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        leave = self.get_object()
        if leave.status not in (LeaveStatus.REQUESTED, LeaveStatus.APPROVED):
            return Response({"detail": "Only requested or approved leave can be cancelled."}, status=400)
        principal = self.principal()
        with transaction.atomic():
            leave.status = LeaveStatus.CANCELLED
            leave.updated_by = principal.principal_id
            leave.save(update_fields=["status", "updated_by", "row_version"])
            self._audit(leave, AuditAction.LEAVE_CANCELLED, "Leave cancelled")
        return Response(self.get_serializer(leave).data)
