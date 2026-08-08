from __future__ import annotations

from django.db import IntegrityError, transaction
from rest_framework.decorators import action
from rest_framework.exceptions import APIException, PermissionDenied, ValidationError
from rest_framework.response import Response

from core.api.viewsets import TenantModelViewSet
from contexts.audit.models import AuditAction
from contexts.audit.recording import record_event
from contexts.notifications.services import notify_work_assigned
from contexts.identity.access import caller_role, is_executive

from . import recommendation as recommendation_service
from . import reviewer_resolution
from .models import (
    AssignmentDecision,
    AssignmentEvent,
    AssignmentEventType,
    ReviewerRule,
)
from .serializers import (
    AssignmentDecisionSerializer,
    AssignmentEventSerializer,
    ReviewerRuleSerializer,
)

_MANAGER_ROLES = {"ADMIN", "PARTNER", "MANAGER"}


class MandatoryAuditPersistenceError(APIException):
    status_code = 503
    default_detail = "The change was not saved because the mandatory audit record could not be persisted."
    default_code = "mandatory_audit_unavailable"


def _is_manager(principal) -> bool:
    return is_executive(principal.tenant_id, principal) or caller_role(principal.tenant_id, principal) in _MANAGER_ROLES


class ReviewerRuleViewSet(TenantModelViewSet):
    queryset = ReviewerRule.objects.all()
    serializer_class = ReviewerRuleSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        for field in ("scope", "scope_ref_id", "level", "service_id", "reviewer_user_id"):
            value = self.request.query_params.get(field)
            if value:
                qs = qs.filter(**{field: value})
        return qs

    def _guard(self):
        if not _is_manager(self.principal()):
            raise PermissionDenied("You are not permitted to manage reviewer hierarchy.")

    def perform_create(self, serializer):
        self._guard()
        principal = self.principal()
        try:
            instance = serializer.save(
                tenant_id=principal.tenant_id,
                created_by=principal.principal_id,
                updated_by=principal.principal_id,
            )
        except IntegrityError as exc:
            raise ValidationError(
                {"level": "An active reviewer rule already exists for this scope and level."}
            ) from exc
        self._audit(instance, "Reviewer rule created")

    def perform_update(self, serializer):
        self._guard()
        instance = serializer.save(updated_by=self.principal().principal_id)
        self._audit(instance, "Reviewer rule updated")

    def _audit(self, instance, summary):
        principal = self.principal()
        try:
            record_event(
                tenant_id=instance.tenant_id,
                principal_id=principal.principal_id,
                action=AuditAction.REVIEWER_HIERARCHY_CHANGED,
                entity_type="ReviewerRule",
                entity_id=instance.id,
                summary=summary,
                new={"scope": instance.scope, "level": instance.level, "reviewer_user_id": str(instance.reviewer_user_id)},
                request=self.request,
            )
        except Exception as exc:  # noqa: BLE001
            raise MandatoryAuditPersistenceError() from exc

    @action(detail=False, methods=["get"])
    def resolve(self, request):
        """Resolve the reviewer chain for a work context (read-only, deterministic)."""
        principal = self.principal()
        context = {
            "work_item_id": request.query_params.get("work_item_id"),
            "service_id": request.query_params.get("service_id"),
            "task_template_id": request.query_params.get("task_template_id"),
            "team_id": request.query_params.get("team_id"),
            "owner_user_id": request.query_params.get("owner_user_id"),
        }
        context = {k: v for k, v in context.items() if v}
        return Response(reviewer_resolution.resolve_reviewer_chain(principal.tenant_id, context))


class AssignmentDecisionViewSet(TenantModelViewSet):
    queryset = AssignmentDecision.objects.all()
    serializer_class = AssignmentDecisionSerializer
    http_method_names = ["get", "head", "options"]

    def get_queryset(self):
        qs = super().get_queryset()
        work_item_id = self.request.query_params.get("work_item_id")
        return qs.filter(work_item_id=work_item_id) if work_item_id else qs


class AssignmentEventViewSet(TenantModelViewSet):
    queryset = AssignmentEvent.objects.all()
    serializer_class = AssignmentEventSerializer
    http_method_names = ["get", "head", "options"]

    def get_queryset(self):
        qs = super().get_queryset()
        work_item_id = self.request.query_params.get("work_item_id")
        return qs.filter(work_item_id=work_item_id) if work_item_id else qs


class AssignmentRecommendationViewSet(TenantModelViewSet):
    """Transient recommendations + authorized execution.

    This viewset defines no model list; it exposes two actions:
    - recommend: deterministic, explainable ranking (never assigns).
    - execute: apply a human-approved owner/reviewer, persist the decision, and
      write the append-only AssignmentEvent + audit.
    """

    queryset = AssignmentEvent.objects.none()
    serializer_class = AssignmentEventSerializer

    def get_queryset(self):
        return AssignmentEvent.objects.filter(tenant_id=self.principal().tenant_id).none()

    @action(detail=False, methods=["post"])
    def recommend(self, request):
        """Compute a transient recommendation. Does NOT assign anything."""
        principal = self.principal()
        context = dict(request.data or {})
        result = recommendation_service.recommend(principal.tenant_id, context)
        return Response(result)

    @action(detail=False, methods=["post"])
    def execute(self, request):
        """Apply an approved assignment to a work item (human-approved only).

        Body: work_item_id (required), owner_user_id, reviewer_user_id,
        was_override, override_reason, recommended_owner_user_id, explanation.
        Requires a management capability. Applies owner/reviewer to the WorkItem
        using the existing representation, persists an AssignmentDecision, writes
        an AssignmentEvent, and records a mandatory audit event.
        """
        from contexts.work.models import WorkItem

        principal = self.principal()
        if not _is_manager(principal):
            raise PermissionDenied("You are not permitted to execute assignments.")

        data = request.data or {}
        work_item_id = data.get("work_item_id")
        if not work_item_id:
            return Response({"detail": "work_item_id is required."}, status=400)
        item = WorkItem.objects.filter(tenant_id=principal.tenant_id, id=work_item_id).first()
        if item is None:
            return Response({"detail": "Work item not found."}, status=404)
        if item.status in ("COMPLETED", "CANCELLED"):
            return Response({"detail": "Cannot assign completed or cancelled work."}, status=400)

        owner = data.get("owner_user_id") or None
        reviewer = data.get("reviewer_user_id") or None
        was_override = bool(data.get("was_override", False))
        override_reason = data.get("override_reason", "")
        if was_override and not override_reason:
            return Response({"detail": "override_reason is required when overriding a recommendation."}, status=400)

        previous_owner_user_id = item.owner_user_id

        with transaction.atomic():
            update_fields = {"updated_by"}
            if owner is not None:
                item.owner_user_id = owner
                update_fields.add("owner_user_id")
            if reviewer is not None:
                item.reviewer_user_id = reviewer
                update_fields.add("reviewer_user_id")
            item.updated_by = principal.principal_id
            item.save(update_fields=list({*update_fields, "row_version"}))

            # Deactivate any prior active decision, then persist the new one.
            AssignmentDecision.objects.filter(
                tenant_id=principal.tenant_id, work_item_id=item.id, is_active=True
            ).update(is_active=False)
            decision = AssignmentDecision.objects.create(
                tenant_id=principal.tenant_id,
                created_by=principal.principal_id,
                updated_by=principal.principal_id,
                work_item_id=item.id,
                selected_owner_user_id=owner,
                selected_reviewer_user_id=reviewer,
                was_override=was_override,
                override_reason=override_reason,
                recommended_owner_user_id=data.get("recommended_owner_user_id") or None,
                explanation=data.get("explanation") or {},
                decided_by=principal.principal_id,
            )
            AssignmentEvent.objects.create(
                tenant_id=principal.tenant_id,
                created_by=principal.principal_id,
                updated_by=principal.principal_id,
                work_item_id=item.id,
                event_type=(
                    AssignmentEventType.OVERRIDE_APPLIED if was_override else AssignmentEventType.RECOMMENDED_APPLIED
                ),
                owner_user_id=owner,
                reviewer_user_id=reviewer,
                was_override=was_override,
                reason=override_reason,
                actor_user_id=principal.principal_id,
                detail={"decision_id": str(decision.id)},
            )
            try:
                record_event(
                    tenant_id=principal.tenant_id,
                    principal_id=principal.principal_id,
                    action=AuditAction.ASSIGNMENT_EXECUTED,
                    entity_type="WorkItem",
                    entity_id=item.id,
                    summary="Assignment executed" + (" (override)" if was_override else ""),
                    new={"owner_user_id": str(owner or ""), "reviewer_user_id": str(reviewer or "")},
                    request=self.request,
                )
                if was_override:
                    record_event(
                        tenant_id=principal.tenant_id,
                        principal_id=principal.principal_id,
                        action=AuditAction.RECOMMENDATION_OVERRIDDEN,
                        entity_type="WorkItem",
                        entity_id=item.id,
                        summary="Recommendation overridden",
                        new={"override_reason": override_reason[:300]},
                        request=self.request,
                    )
            except Exception as exc:  # noqa: BLE001
                raise MandatoryAuditPersistenceError() from exc

        if (
            owner is not None
            and str(previous_owner_user_id or "")
            != str(item.owner_user_id or "")
        ):
            notify_work_assigned(
                item=item,
                actor_principal_id=principal.principal_id,
            )

        return Response(
            {
                "work_item_id": str(item.id),
                "owner_user_id": str(item.owner_user_id or ""),
                "reviewer_user_id": str(item.reviewer_user_id or ""),
                "decision_id": str(decision.id),
                "was_override": was_override,
            },
            status=201,
        )
