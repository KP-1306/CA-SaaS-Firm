from __future__ import annotations

from django.db import transaction
from rest_framework.exceptions import ValidationError

from core.api.viewsets import TenantModelViewSet
from contexts.audit.models import AuditAction
from contexts.audit.recording import record_event
from contexts.audit.viewset_mixins import AuditedTenantViewSetMixin, MandatoryAuditPersistenceError

from .models import (
    Branch,
    Department,
    Designation,
    FirmProfile,
    ReportingRelationship,
    Team,
    TeamMembership,
)
from .serializers import (
    BranchSerializer,
    DepartmentSerializer,
    DesignationSerializer,
    FirmProfileSerializer,
    ReportingRelationshipSerializer,
    TeamMembershipSerializer,
    TeamSerializer,
)


class FirmProfileViewSet(TenantModelViewSet):
    queryset = FirmProfile.objects.all()
    serializer_class = FirmProfileSerializer
    search_fields = ["name", "legal_name", "pan", "gstin"]


class BranchViewSet(TenantModelViewSet):
    queryset = Branch.objects.all()
    serializer_class = BranchSerializer
    search_fields = ["name", "code", "email", "mobile"]


class TeamViewSet(TenantModelViewSet):
    queryset = Team.objects.all()
    serializer_class = TeamSerializer
    search_fields = ["name", "code"]


class DepartmentViewSet(AuditedTenantViewSetMixin, TenantModelViewSet):
    queryset = Department.objects.all()
    serializer_class = DepartmentSerializer
    search_fields = ["name", "code"]
    audit_entity_type = "Department"
    audit_summary_fields = ("name", "code", "status")
    audit_create_action = AuditAction.ORG_STRUCTURE_CHANGED
    audit_update_action = AuditAction.ORG_STRUCTURE_CHANGED

    def get_queryset(self):
        qs = super().get_queryset()
        status = self.request.query_params.get("status")
        return qs.filter(status=status) if status else qs


class DesignationViewSet(AuditedTenantViewSetMixin, TenantModelViewSet):
    queryset = Designation.objects.all()
    serializer_class = DesignationSerializer
    search_fields = ["name", "code"]
    audit_entity_type = "Designation"
    audit_summary_fields = ("name", "code", "status")
    audit_create_action = AuditAction.ORG_STRUCTURE_CHANGED
    audit_update_action = AuditAction.ORG_STRUCTURE_CHANGED


class TeamMembershipViewSet(TenantModelViewSet):
    queryset = TeamMembership.objects.all()
    serializer_class = TeamMembershipSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        for field in ("employee_id", "team_id"):
            value = self.request.query_params.get(field)
            if value:
                qs = qs.filter(**{field: value})
        return qs

    def perform_create(self, serializer):
        from django.db import IntegrityError

        principal = self.principal()
        try:
            with transaction.atomic():
                instance = serializer.save(
                    tenant_id=principal.tenant_id,
                    created_by=principal.principal_id,
                    updated_by=principal.principal_id,
                )
        except IntegrityError as exc:
            raise ValidationError(
                {"team_id": "This employee already has an active membership for this team."}
            ) from exc
        try:
            record_event(
                tenant_id=instance.tenant_id,
                principal_id=principal.principal_id,
                action=AuditAction.ORG_STRUCTURE_CHANGED,
                entity_type="TeamMembership",
                entity_id=instance.id,
                summary="Team membership created",
                new={"employee_id": str(instance.employee_id), "team_id": str(instance.team_id)},
                request=self.request,
            )
        except Exception as exc:  # noqa: BLE001
            raise MandatoryAuditPersistenceError() from exc


def _would_create_cycle(tenant_id, employee_id, manager_id) -> bool:
    """Walk the active PRIMARY chain up from manager; a cycle exists if we reach employee."""
    if employee_id is None or manager_id is None:
        return employee_id == manager_id
    seen = set()
    current = manager_id
    while current is not None and current not in seen:
        if current == employee_id:
            return True
        seen.add(current)
        nxt = (
            ReportingRelationship.objects.filter(
                tenant_id=tenant_id, employee_id=current, relation_type="PRIMARY", is_active=True
            )
            .values_list("manager_id", flat=True)
            .first()
        )
        current = nxt
    return False


class ReportingRelationshipViewSet(TenantModelViewSet):
    queryset = ReportingRelationship.objects.all()
    serializer_class = ReportingRelationshipSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        for field in ("employee_id", "manager_id", "relation_type"):
            value = self.request.query_params.get(field)
            if value:
                qs = qs.filter(**{field: value})
        return qs

    def _guard(self, serializer):
        principal = self.principal()
        employee_id = serializer.validated_data.get(
            "employee_id", getattr(serializer.instance, "employee_id", None)
        )
        manager_id = serializer.validated_data.get(
            "manager_id", getattr(serializer.instance, "manager_id", None)
        )
        relation_type = serializer.validated_data.get(
            "relation_type", getattr(serializer.instance, "relation_type", "PRIMARY")
        )
        if employee_id == manager_id:
            raise ValidationError({"manager_id": "An employee cannot report to themselves."})
        # Only PRIMARY lines form the authority tree we cycle-check.
        if relation_type == "PRIMARY" and _would_create_cycle(principal.tenant_id, employee_id, manager_id):
            raise ValidationError({"manager_id": "This would create a circular reporting relationship."})

    def perform_create(self, serializer):
        from django.db import IntegrityError

        self._guard(serializer)
        principal = self.principal()
        try:
            with transaction.atomic():
                instance = serializer.save(
                    tenant_id=principal.tenant_id,
                    created_by=principal.principal_id,
                    updated_by=principal.principal_id,
                )
        except IntegrityError as exc:
            raise ValidationError(
                {"relation_type": "An active primary reporting line already exists for this employee."}
            ) from exc
        self._audit(instance, "Reporting relationship created")

    def perform_update(self, serializer):
        self._guard(serializer)
        instance = serializer.save(updated_by=self.principal().principal_id)
        self._audit(instance, "Reporting relationship updated")

    def _audit(self, instance, summary):
        principal = self.principal()
        try:
            record_event(
                tenant_id=instance.tenant_id,
                principal_id=principal.principal_id,
                action=AuditAction.MANAGER_CHANGED,
                entity_type="ReportingRelationship",
                entity_id=instance.id,
                summary=summary,
                new={"employee_id": str(instance.employee_id), "manager_id": str(instance.manager_id), "relation_type": instance.relation_type},
                request=self.request,
            )
        except Exception as exc:  # noqa: BLE001
            raise MandatoryAuditPersistenceError() from exc
