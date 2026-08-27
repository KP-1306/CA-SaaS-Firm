from __future__ import annotations

from rest_framework.permissions import IsAuthenticated
from contexts.configuration.models import Domain, Service
from contexts.authorization.permissions import (
    DocumentAttachmentAccessPermission,
    DocumentRequestAccessPermission,
    WorkItemAccessPermission,
)
import hashlib
import os
import uuid
from datetime import timedelta

from django.db import models, transaction
from django.http import FileResponse, Http404
from django.utils import timezone
from rest_framework import status as http_status
from rest_framework.decorators import action
from rest_framework.exceptions import (
    APIException,
    PermissionDenied,
    ValidationError,
)
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response

from core.api.viewsets import TenantModelViewSet
from contexts.clients.models import ClientContact
from contexts.configuration.models import (
    ServiceDocumentRequirement,
    ServiceDocumentRequirementSet,
    ServiceProcessStep,
)
from contexts.assignment.models import AssignmentEvent
from contexts.identity.models import Employee
from contexts.quality.services import (
    cycle_summary as qa_cycle_summary,
    mark_approved as qa_mark_approved,
    mark_changes_requested as qa_mark_changes_requested,
    mark_submitted as qa_mark_submitted,
    prepare_cycle as qa_prepare_cycle,
    qa_readiness,
    raise_issue as qa_raise_issue,
    resolve_issue as qa_resolve_issue,
    review_history as qa_review_history,
    save_responses as qa_save_responses,
)

from . import ownership
from .document_intelligence import calculate_document_readiness
from .work_health import calculate_work_health
from contexts.audit.recording import record_event
from contexts.notifications.services import (
    notify_work_assigned,
    notify_work_transition,
)
from contexts.audit.models import AuditAction, AuditEvent

from .models import (
    AttachmentReviewStatus,
    DocumentAttachment,
    DuplicateResolutionStatus,
    DocumentRequest,
    DocumentRequestStatus,
    WorkItem,
    WorkProcessState,
    WorkNote,
    WorkStatus,
    document_request_is_complete,
    recalculate_document_request_status,
)
from .serializers import (
    DocumentAttachmentSerializer,
    DocumentRequestSerializer,
    WorkItemSerializer,
    WorkNoteSerializer,
)

# Explicit lifecycle. WAITING_FOR_CLIENT is a distinct state.
# Note: READY_FOR_REVIEW -> COMPLETED is intentionally NOT in this generic map;
# completion happens only through the explicit ``approve`` action.
_ALLOWED_TRANSITIONS = {
    WorkStatus.NOT_STARTED: {WorkStatus.IN_PROGRESS, WorkStatus.CANCELLED},
    WorkStatus.IN_PROGRESS: {
        WorkStatus.WAITING_FOR_CLIENT,
        WorkStatus.READY_FOR_REVIEW,
        WorkStatus.CANCELLED,
    },
    WorkStatus.WAITING_FOR_CLIENT: {WorkStatus.IN_PROGRESS, WorkStatus.CANCELLED},
    WorkStatus.READY_FOR_REVIEW: set(),
    WorkStatus.REWORK_REQUIRED: {WorkStatus.IN_PROGRESS, WorkStatus.CANCELLED},
    WorkStatus.COMPLETED: set(),
    WorkStatus.CANCELLED: set(),
}

_MANDATORY_DOCS_MSG = (
    "All mandatory document requests must be accepted or waived before completion."
)

_ALLOWED_EXT_MIME = {
    ".pdf": {"application/pdf"},
    ".png": {"image/png"},
    ".jpg": {"image/jpeg"},
    ".jpeg": {"image/jpeg"},
    ".webp": {"image/webp"},
    ".csv": {"text/csv", "application/csv", "text/plain"},
    ".txt": {"text/plain"},
    ".xlsx": {"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"},
    ".xls": {"application/vnd.ms-excel"},
    ".docx": {"application/vnd.openxmlformats-officedocument.wordprocessingml.document"},
    ".doc": {"application/msword"},
}
_BLOCKED_EXTENSIONS = {
    ".exe", ".bat", ".cmd", ".sh", ".com", ".msi", ".dll", ".scr", ".js",
    ".jar", ".ps1", ".vbs", ".php", ".py", ".pl", ".app", ".bin",
}
_MAX_UPLOAD_BYTES = 15 * 1024 * 1024


class DuplicateAttachmentError(ValueError):
    """Raised when uploaded content already exists in the same scope."""

    def __init__(self, attachment):
        self.attachment = attachment
        super().__init__(
            "This exact file already exists for the selected "
            "document request."
        )


class MandatoryAuditPersistenceError(APIException):
    """Fail closed when a mandatory audit event cannot be persisted."""

    status_code = 503
    default_detail = (
        "The requested change was not saved because the mandatory audit record "
        "could not be persisted. Please retry later."
    )
    default_code = "mandatory_audit_unavailable"


def _sanitise_filename(name: str) -> str:
    """Keep a readable basename only; strip any path components."""
    base = os.path.basename(name.replace("\\", "/"))
    safe = "".join(c for c in base if c.isalnum() or c in " ._-()").strip()
    return (safe or "file")[:255]


def _validated_upload(upload):
    if upload.size > _MAX_UPLOAD_BYTES:
        raise ValueError("File exceeds the 15 MB limit.")
    original = _sanitise_filename(upload.name)
    ext = os.path.splitext(original)[1].lower()
    if ext in _BLOCKED_EXTENSIONS or ext not in _ALLOWED_EXT_MIME:
        raise ValueError("This file type is not permitted.")
    declared = (upload.content_type or "").lower()
    if declared and declared not in _ALLOWED_EXT_MIME[ext]:
        raise ValueError("The file content type does not match its extension.")
    upload.name = f"{uuid.uuid4().hex}{ext}"
    return original, declared


def _sha256_upload(upload) -> str:
    """Return an immutable content fingerprint without consuming the upload."""
    digest = hashlib.sha256()

    if hasattr(upload, "chunks"):
        for chunk in upload.chunks():
            digest.update(chunk)
    else:
        while True:
            chunk = upload.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)

    upload.seek(0)
    return digest.hexdigest()


def _attachment_scope(*, principal, document_request_id, work_item_id):
    queryset = DocumentAttachment.objects.filter(
        tenant_id=principal.tenant_id,
    )

    if document_request_id:
        return queryset.filter(
            document_request_id=document_request_id,
        )

    if work_item_id:
        return queryset.filter(
            work_item_id=work_item_id,
            document_request_id__isnull=True,
        )

    return queryset.none()


def _create_attachment(
    *,
    principal,
    upload,
    document_request_id=None,
    work_item_id=None,
    source="INTERNAL_TEAM",
    upload_intent="NEW_VERSION",
    allow_duplicate=False,
):
    original, declared = _validated_upload(upload)
    content_hash = _sha256_upload(upload)

    scoped = _attachment_scope(
        principal=principal,
        document_request_id=document_request_id,
        work_item_id=work_item_id,
    )

    duplicate = (
        scoped.filter(sha256=content_hash)
        .order_by("-created_at", "-id")
        .first()
    )

    if duplicate is not None and not allow_duplicate:
        raise DuplicateAttachmentError(duplicate)

    latest = (
        scoped.order_by(
            "-version_number",
            "-created_at",
            "-id",
        )
        .first()
    )

    if upload_intent not in {
        "NEW_VERSION",
        "SEPARATE_DOCUMENT",
    }:
        raise ValueError(
            "Upload intent must be NEW_VERSION or "
            "SEPARATE_DOCUMENT."
        )

    if upload_intent == "NEW_VERSION":
        next_version = (
            latest.version_number + 1
            if latest
            else 1
        )
        supersedes_id = latest.id if latest else None
    else:
        next_version = 1
        supersedes_id = None

    is_duplicate = duplicate is not None

    attachment = DocumentAttachment(
        tenant_id=principal.tenant_id,
        created_by=principal.principal_id,
        updated_by=principal.principal_id,
        document_request_id=document_request_id,
        work_item_id=work_item_id,
        source=source,
        uploaded_by=principal.principal_id,
        original_name=original,
        content_type=declared,
        size_bytes=upload.size,
        file=upload,
        sha256=content_hash,
        version_number=next_version,
        version_label=f"V{next_version}",
        supersedes_attachment_id=supersedes_id,
        duplicate_of_attachment_id=(
            duplicate.id
            if duplicate
            else None
        ),
        is_duplicate=is_duplicate,
        duplicate_resolution=(
            DuplicateResolutionStatus.UNRESOLVED
            if is_duplicate
            else DuplicateResolutionStatus.NOT_APPLICABLE
        ),
        is_canonical=latest is None and not is_duplicate,
    )

    attachment.save()

    return attachment


class WorkItemViewSet(TenantModelViewSet):
    permission_classes = [
        IsAuthenticated,
        WorkItemAccessPermission,
    ]
    queryset = WorkItem.objects.all()
    serializer_class = WorkItemSerializer
    search_fields = ["title", "period", "notes", "description"]
    ordering_fields = ["due_date", "created_at", "status", "priority"]

    def _eligible_document_contact(self, item):
        contacts = ClientContact.objects.filter(
            tenant_id=item.tenant_id,
            client_id=item.client_id,
            is_active=True,
            can_receive_document_requests=True,
        )

        return (
            contacts.filter(is_primary=True)
            .order_by("created_at", "id")
            .first()
            or contacts.order_by("created_at", "id").first()
        )

    def _active_requirement_set(self, item):
        if not item.service_id:
            return None

        today = timezone.now().date()

        return (
            ServiceDocumentRequirementSet.objects.filter(
                tenant_id=item.tenant_id,
                service_id=item.service_id,
                status="ACTIVE",
            )
            .filter(
                models.Q(effective_from__isnull=True)
                | models.Q(effective_from__lte=today)
            )
            .filter(
                models.Q(effective_until__isnull=True)
                | models.Q(effective_until__gte=today)
            )
            .order_by(
                "-version_number",
                "-effective_from",
                "-created_at",
            )
            .first()
        )

    def _generate_document_requests(
        self,
        item,
        *,
        request_data=None,
        strict=False,
    ):
        principal = self.principal()
        request_data = request_data or {}

        requirement_set = self._active_requirement_set(item)

        if requirement_set is None:
            if strict:
                raise ValidationError(
                    {
                        "detail": (
                            "No active document requirement set exists "
                            "for this service."
                        )
                    }
                )

            return {
                "created": 0,
                "existing": 0,
                "skipped": "NO_ACTIVE_REQUIREMENT_SET",
                "requests": [],
            }

        contact = self._eligible_document_contact(item)

        requirements = list(
            ServiceDocumentRequirement.objects.filter(
                tenant_id=item.tenant_id,
                service_id=item.service_id,
                requirement_set_id=requirement_set.id,
                is_active=True,
            ).order_by(
                "display_order",
                "name",
                "id",
            )
        )

        financial_year = str(
            request_data.get("financial_year", "")
        ).strip()

        assessment_year = str(
            request_data.get("assessment_year", "")
        ).strip()

        filing_period = str(
            request_data.get(
                "filing_period",
                item.period or "",
            )
        ).strip()

        request_channel = str(
            request_data.get(
                "request_channel",
                "WHATSAPP",
            )
        ).strip() or "WHATSAPP"

        created_count = 0
        existing_count = 0
        generated = []

        with transaction.atomic():
            for requirement in requirements:
                defaults = {
                    "created_by": principal.principal_id,
                    "updated_by": principal.principal_id,
                    "name": requirement.name,
                    "description": requirement.description,
                    "client_id": item.client_id,
                    "source_requirement_set_id": requirement_set.id,
                    "auto_generated": True,
                    "category": requirement.category,
                    "financial_year": (
                        financial_year
                        if requirement.financial_year_required
                        else ""
                    ),
                    "assessment_year": (
                        assessment_year
                        if requirement.assessment_year_required
                        else ""
                    ),
                    "filing_period": (
                        filing_period
                        if requirement.filing_period_required
                        else ""
                    ),
                    "requested_date": timezone.now().date(),
                    "due_date": item.due_date,
                    "requested_from_contact_id": (
                        contact.id if contact is not None else None
                    ),
                    "request_channel": request_channel,
                    "sent_at": (
                        timezone.now()
                        if contact is not None
                        else None
                    ),
                    "mandatory": requirement.mandatory,
                    "client_visible": True,
                    "remarks": (
                        "Automatically generated from "
                        f"{requirement_set.name} "
                        f"V{requirement_set.version_number}."
                    ),
                }

                document_request, created = (
                    DocumentRequest.objects.get_or_create(
                        tenant_id=item.tenant_id,
                        work_item_id=item.id,
                        source_requirement_id=requirement.id,
                        defaults=defaults,
                    )
                )

                generated.append(document_request)

                if created:
                    created_count += 1

                    try:
                        record_event(
                            tenant_id=item.tenant_id,
                            principal_id=principal.principal_id,
                            action=AuditAction.DOCUMENT_REQUEST_CREATED,
                            entity_type="DocumentRequest",
                            entity_id=document_request.id,
                            summary=document_request.name,
                            new={
                                "name": document_request.name,
                                "status": document_request.status,
                                "auto_generated": True,
                                "source_requirement_id": str(
                                    requirement.id
                                ),
                                "work_item_id": str(item.id),
                            },
                            request=self.request,
                        )
                    except Exception as exc:
                        raise MandatoryAuditPersistenceError() from exc
                else:
                    existing_count += 1

            if created_count:
                suffix = "" if created_count == 1 else "s"

                self._record(
                    item,
                    (
                        f"Automatically generated {created_count} "
                        f"document request{suffix} from "
                        f"{requirement_set.name} "
                        f"V{requirement_set.version_number}."
                    ),
                )

        return {
            "created": created_count,
            "existing": existing_count,
            "skipped": "",
            "requirement_set_id": str(requirement_set.id),
            "requirement_set_name": requirement_set.name,
            "requirement_set_version": (
                requirement_set.version_number
            ),
            "requests": generated,
        }

    def perform_create(self, serializer):
        principal = self.principal()

        with transaction.atomic():
            item = serializer.save(
                tenant_id=principal.tenant_id,
                created_by=principal.principal_id,
                updated_by=principal.principal_id,
            )

            self._generate_document_requests(
                item,
                request_data=self.request.data,
                strict=False,
            )

            # Mudra loan work initializes its durable runtime position at the
            # APPLICATION system stage on creation, so the tracker shows the
            # authoritative starting stage immediately. Non-Mudra work is
            # unaffected (Udyam and generic work keep their existing behavior).
            if self._is_mudra_loan(item):
                application_step = self._mudra_process_step(item, "APPLICATION")
                if application_step is not None:
                    existing_state = (
                        WorkProcessState.objects
                        .filter(
                            tenant_id=principal.tenant_id,
                            work_item_id=item.id,
                        )
                        .first()
                    )
                    if existing_state is None:
                        self._persist_automated_process_step(
                            item,
                            application_step,
                            principal,
                            "Mudra case initialized at Application & KYC.",
                        )

    @action(
        detail=True,
        methods=["post"],
        url_path="generate-document-requests",
    )
    def generate_document_requests(self, request, pk=None):
        item = self.get_object()

        if not ownership.can_mutate_document_request(
            item,
            self.principal(),
        ):
            raise PermissionDenied(
                "Document requests can only be generated by the "
                "assigned owner while the work item is editable."
            )

        result = self._generate_document_requests(
            item,
            request_data=request.data,
            strict=True,
        )

        return Response(
            {
                "created": result["created"],
                "existing": result["existing"],
                "requirement_set_id": (
                    result["requirement_set_id"]
                ),
                "requirement_set_name": (
                    result["requirement_set_name"]
                ),
                "requirement_set_version": (
                    result["requirement_set_version"]
                ),
                "requests": DocumentRequestSerializer(
                    result["requests"],
                    many=True,
                    context={"request": request},
                ).data,
            },
            status=http_status.HTTP_200_OK,
        )

    def get_queryset(self):
        vertical_id = self.request.query_params.get(
            "vertical_id"
        )
        qs = super().get_queryset()
        params = self.request.query_params
        for field in ("status", "priority", "client_id", "service_id", "owner_user_id", "reviewer_user_id"):
            value = params.get(field)
            if value:
                qs = qs.filter(**{field: value})
        if vertical_id:
            service_ids = Service.objects.filter(
                tenant_id=self.principal().tenant_id,
                domain_id__in=Domain.objects.filter(
                    tenant_id=self.principal().tenant_id,
                    vertical_id=vertical_id,
                ).values_list("id", flat=True),
            ).values_list("id", flat=True)

            qs = qs.filter(
                service_id__in=service_ids
            )

        return qs

    # -- C4 controller guards ------------------------------------------
    _CONTROL_FIELDS = ("status", "owner_user_id", "reviewer_user_id")

    def _deny_control_field_writes(self, item):
        """Reject generic writes to workflow/ownership control fields."""
        data = getattr(self.request, "data", {}) or {}
        for field in self._CONTROL_FIELDS:
            if field in data and str(data.get(field)) != str(getattr(item, field)):
                raise PermissionDenied(
                    f"{field} cannot be changed through a generic update; "
                    "use the dedicated workflow action."
                )

    def _deny_operational_data_writes(self, item):
        """Freeze captured operational details after Work creation.

        Generic edits may change operational_data only for the canonical
        tenant-local operational superuser. Dedicated workflow actions that
        persist lifecycle evidence do not use this generic update path.
        """
        data = getattr(self.request, "data", {}) or {}

        if "operational_data" not in data:
            return

        incoming = data.get("operational_data")
        current = item.operational_data or {}

        if incoming == current:
            return

        if ownership.is_operational_superuser(
            item.tenant_id,
            self.principal(),
        ):
            return

        raise PermissionDenied(
            "Operational details are read-only after Work creation."
        )

    def update(self, request, *args, **kwargs):
        item = self.get_object()
        if not ownership.can_edit_work_item(item, self.principal()):
            raise PermissionDenied(
                "This work item is read-only for you at its current stage."
            )
        self._deny_control_field_writes(item)

        # Udyam process-owned lifecycle evidence is protected by the serializer
        # ownership boundary (WorkItemSerializer.validate): for the Udyam
        # service the reserved keys are always preserved from the database
        # instance and incoming values for them are ignored.  No request-level
        # re-injection workaround is required here.

        self._deny_operational_data_writes(item)
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        kwargs["partial"] = True  # preserve true PATCH partial semantics
        return self.update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        # C4: deletion is never permitted; existing DELETE would destroy
        # attachment/review/audit history. Blocked rather than soft-deleted.
        raise PermissionDenied("Deleting work items is not permitted.")

    # -- helpers -------------------------------------------------------
    def _record(self, item, entry, from_status="", to_status=""):
        principal = self.principal()
        WorkNote.objects.create(
            tenant_id=principal.tenant_id,
            created_by=principal.principal_id,
            updated_by=principal.principal_id,
            work_item_id=item.id,
            author_user_id=principal.principal_id,
            entry=entry,
            from_status=from_status,
            to_status=to_status,
        )

    def _unresolved_mandatory_docs(self, item):
        requests = DocumentRequest.objects.filter(
            tenant_id=item.tenant_id,
            work_item_id=item.id,
            mandatory=True,
        )
        return sum(1 for document_request in requests if not document_request_is_complete(document_request))

    def _require_reviewer(self, item):
        principal = self.principal()

        if not ownership.is_reviewer(
            item,
            principal,
        ):
            raise PermissionDenied(
                "Only the assigned reviewer or a platform administrator "
                "may perform this action."
            )

    def _transition(self, item, target, entry, *, update_fields):
        previous = item.status

        # Business mutation, WorkNote and mandatory audit are one DB unit.
        # If mandatory audit persistence fails, the business mutation rolls back.
        with transaction.atomic():
            item.status = target
            fields = {"status", "updated_by", *update_fields}
            item.updated_by = self.principal().principal_id
            item.save(update_fields=list(fields))
            self._record(
                item,
                entry or f"Status changed to {target}.",
                previous,
                target,
            )
            try:
                record_event(
                    tenant_id=item.tenant_id,
                    principal_id=self.principal().principal_id,
                    action=AuditAction.STATUS_CHANGE,
                    entity_type="WorkItem",
                    entity_id=item.id,
                    summary=f"{previous} -> {target}",
                    previous={"status": previous},
                    new={"status": target},
                    request=self.request,
                )
            except Exception as exc:
                raise MandatoryAuditPersistenceError() from exc

        # Notification is not part of mandatory DB consistency.
        notify_work_transition(
            item=item,
            previous_status=previous,
            target_status=target,
            actor_principal_id=self.principal().principal_id,
        )

        return previous


    # -- automated service-process helpers -----------------------------
    def _is_udyam_registration(self, item) -> bool:
        """Identify the configured Udyam registration service."""
        if not item.service_id:
            return False

        return Service.objects.filter(
            tenant_id=item.tenant_id,
            id=item.service_id,
            code="UDYAM_REGISTRATION",
        ).exists()

    def _udyam_process_step(self, item, code):
        """Resolve one active configured Udyam process step."""
        if not item.service_id:
            return None

        return (
            ServiceProcessStep.objects
            .filter(
                tenant_id=item.tenant_id,
                service_id=item.service_id,
                code=code,
                is_active=True,
            )
            .first()
        )

    def _persist_automated_process_step(
        self,
        item,
        target_step,
        principal,
        note,
    ):
        """
        Persist process position derived from an actual workflow action.

        This mirrors the existing process-step persistence semantics without
        creating a second workflow engine or issuing an internal HTTP request.
        """
        state = (
            WorkProcessState.objects
            .select_for_update()
            .filter(
                tenant_id=principal.tenant_id,
                work_item_id=item.id,
            )
            .first()
        )

        previous_step = None

        if state is not None and state.current_step_id:
            previous_step = (
                ServiceProcessStep.objects
                .filter(
                    tenant_id=principal.tenant_id,
                    service_id=item.service_id,
                    id=state.current_step_id,
                )
                .first()
            )

        now = timezone.now()

        if state is None:
            state = WorkProcessState.objects.create(
                tenant_id=principal.tenant_id,
                created_by=principal.principal_id,
                updated_by=principal.principal_id,
                work_item_id=item.id,
                current_step_id=target_step.id,
                entered_at=now,
                entered_by=principal.principal_id,
                note=note,
            )
        else:
            state.current_step_id = target_step.id
            state.entered_at = now
            state.entered_by = principal.principal_id
            state.note = note
            state.updated_by = principal.principal_id
            state.save(
                update_fields=[
                    "current_step_id",
                    "entered_at",
                    "entered_by",
                    "note",
                    "updated_by",
                    "row_version",
                ]
            )

        previous_payload = {
            "process_step_id": (
                str(previous_step.id)
                if previous_step is not None
                else ""
            ),
            "process_step_code": (
                previous_step.code
                if previous_step is not None
                else ""
            ),
        }

        new_payload = {
            "process_step_id": str(target_step.id),
            "process_step_code": target_step.code,
        }

        try:
            record_event(
                tenant_id=principal.tenant_id,
                principal_id=principal.principal_id,
                action=AuditAction.STATUS_CHANGE,
                entity_type="WorkProcessState",
                entity_id=state.id,
                summary=(
                    "Process step changed: "
                    f"{previous_step.code if previous_step else 'NONE'} "
                    f"-> {target_step.code}"
                ),
                previous=previous_payload,
                new=new_payload,
                request=self.request,
            )
        except Exception as exc:
            raise MandatoryAuditPersistenceError() from exc

        return state

    # -- service-specific operational process position ----------------
    @action(
        detail=True,
        methods=["get", "post"],
        url_path="process-step",
    )
    def process_step(self, request, pk=None):
        """
        Set the current service-process step for one WorkItem.

        Process position is intentionally independent from
        WorkItem.status.
        """
        item = self.get_object()
        principal = self.principal()

        if request.method == "GET":
            state = (
                WorkProcessState.objects
                .filter(
                    tenant_id=principal.tenant_id,
                    work_item_id=item.id,
                )
                .first()
            )

            if state is None:
                return Response(
                    {
                        "work_item_id": str(item.id),
                        "current_step": None,
                        "entered_at": None,
                        "entered_by": None,
                        "note": "",
                    },
                    status=http_status.HTTP_200_OK,
                )

            current_step = (
                ServiceProcessStep.objects
                .filter(
                    tenant_id=principal.tenant_id,
                    id=state.current_step_id,
                    service_id=item.service_id,
                    is_active=True,
                )
                .first()
            )

            return Response(
                {
                    "work_item_id": str(item.id),
                    "current_step": (
                        {
                            "id": str(current_step.id),
                            "code": current_step.code,
                            "name": current_step.name,
                            "display_order": (
                                current_step.display_order
                            ),
                        }
                        if current_step is not None
                        else None
                    ),
                    "entered_at": (
                        state.entered_at.isoformat()
                        if state.entered_at
                        else None
                    ),
                    "entered_by": str(state.entered_by),
                    "note": state.note,
                },
                status=http_status.HTTP_200_OK,
            )

        if not ownership.is_owner(item, principal):
            raise PermissionDenied(
                "Only the assigned owner may change the process step "
                "of this work item."
            )

        if not item.service_id:
            return Response(
                {
                    "detail": (
                        "A service is required before a process step "
                        "can be selected."
                    ),
                    "code": "PROCESS_SERVICE_REQUIRED",
                },
                status=400,
            )

        data = request.data or {}
        raw_step_id = data.get("step_id")

        if not raw_step_id:
            return Response(
                {
                    "detail": "step_id is required.",
                    "code": "PROCESS_STEP_REQUIRED",
                },
                status=400,
            )

        try:
            step_uuid = uuid.UUID(str(raw_step_id))
        except (TypeError, ValueError, AttributeError):
            return Response(
                {
                    "detail": "step_id must be a valid UUID.",
                    "code": "PROCESS_STEP_INVALID",
                },
                status=400,
            )

        note = str(data.get("note") or "").strip()

        with transaction.atomic():
            locked_item = (
                WorkItem.objects
                .select_for_update()
                .filter(
                    tenant_id=principal.tenant_id,
                    id=item.id,
                )
                .first()
            )

            if locked_item is None:
                raise PermissionDenied(
                    "This work item is no longer available."
                )

            if not ownership.is_owner(
                locked_item,
                principal,
            ):
                raise PermissionDenied(
                    "Only the assigned owner may change the process step "
                    "of this work item."
                )

            if not locked_item.service_id:
                return Response(
                    {
                        "detail": (
                            "A service is required before a process step "
                            "can be selected."
                        ),
                        "code": "PROCESS_SERVICE_REQUIRED",
                    },
                    status=400,
                )

            target_step = (
                ServiceProcessStep.objects
                .filter(
                    tenant_id=principal.tenant_id,
                    id=step_uuid,
                    service_id=locked_item.service_id,
                    is_active=True,
                )
                .first()
            )

            if target_step is None:
                return Response(
                    {
                        "detail": (
                            "The selected process step is not active and "
                            "valid for this work item's service."
                        ),
                        "code": "PROCESS_STEP_NOT_AVAILABLE",
                    },
                    status=400,
                )

            state = (
                WorkProcessState.objects
                .select_for_update()
                .filter(
                    tenant_id=principal.tenant_id,
                    work_item_id=locked_item.id,
                )
                .first()
            )

            previous_step = None

            if (
                state is not None
                and state.current_step_id
            ):
                previous_step = (
                    ServiceProcessStep.objects
                    .filter(
                        tenant_id=principal.tenant_id,
                        id=state.current_step_id,
                    )
                    .first()
                )

            now = timezone.now()

            if state is None:
                state = WorkProcessState.objects.create(
                    tenant_id=principal.tenant_id,
                    created_by=principal.principal_id,
                    updated_by=principal.principal_id,
                    work_item_id=locked_item.id,
                    current_step_id=target_step.id,
                    entered_at=now,
                    entered_by=principal.principal_id,
                    note=note,
                )
            else:
                state.current_step_id = target_step.id
                state.entered_at = now
                state.entered_by = principal.principal_id
                state.note = note
                state.updated_by = principal.principal_id

                state.save(
                    update_fields=[
                        "current_step_id",
                        "entered_at",
                        "entered_by",
                        "note",
                        "updated_by",
                        "row_version",
                    ]
                )

            previous_payload = {
                "process_step_id": (
                    str(previous_step.id)
                    if previous_step is not None
                    else ""
                ),
                "process_step_code": (
                    previous_step.code
                    if previous_step is not None
                    else ""
                ),
            }

            new_payload = {
                "process_step_id": str(target_step.id),
                "process_step_code": target_step.code,
            }

            try:
                record_event(
                    tenant_id=principal.tenant_id,
                    principal_id=principal.principal_id,
                    action=AuditAction.STATUS_CHANGE,
                    entity_type="WorkProcessState",
                    entity_id=state.id,
                    summary=(
                        "Process step changed: "
                        f"{previous_step.code if previous_step else 'NONE'} "
                        f"-> {target_step.code}"
                    ),
                    previous=previous_payload,
                    new=new_payload,
                    request=self.request,
                )
            except Exception as exc:
                raise MandatoryAuditPersistenceError() from exc

        return Response(
            {
                "work_item_id": str(locked_item.id),
                "current_step": {
                    "id": str(target_step.id),
                    "code": target_step.code,
                    "name": target_step.name,
                    "display_order": target_step.display_order,
                },
                "entered_at": state.entered_at.isoformat(),
                "entered_by": str(state.entered_by),
                "note": state.note,
            },
            status=http_status.HTTP_200_OK,
        )

    # -- Udyam post-review business milestones -------------------

    def _require_udyam_owner(self, item):
        principal = self.principal()

        if not self._is_udyam_registration(item):
            raise ValidationError(
                {
                    "detail": "This action is available only for Udyam registration work.",
                    "code": "UDYAM_SERVICE_REQUIRED",
                }
            )

        if not ownership.is_owner(item, principal):
            raise PermissionDenied(
                "Only the assigned owner or a platform administrator "
                "may perform this Udyam action."
            )

        return principal

    def _locked_udyam_process_state(self, item, expected_code):
        state = (
            WorkProcessState.objects
            .select_for_update()
            .filter(
                tenant_id=item.tenant_id,
                work_item_id=item.id,
            )
            .first()
        )

        expected_step = self._udyam_process_step(
            item,
            expected_code,
        )

        if expected_step is None:
            raise ValidationError(
                {
                    "detail": (
                        f"Udyam process step {expected_code} "
                        "is not configured."
                    ),
                    "code": "UDYAM_PROCESS_CONFIGURATION_MISSING",
                }
            )

        if state is None or state.current_step_id != expected_step.id:
            raise ValidationError(
                {
                    "detail": (
                        f"This action requires Udyam process step "
                        f"{expected_code}."
                    ),
                    "code": "UDYAM_PROCESS_POSITION_REQUIRED",
                }
            )

        return state

    @action(
        detail=True,
        methods=["post"],
        url_path="udyam-submit-application",
    )
    def udyam_submit_application(self, request, pk=None):
        item = self.get_object()
        principal = self._require_udyam_owner(item)

        application_reference = str(
            (request.data or {}).get("application_reference") or ""
        ).strip()

        submission_date = str(
            (request.data or {}).get("submission_date") or ""
        ).strip()

        submission_time = str(
            (request.data or {}).get("submission_time") or ""
        ).strip()

        if not application_reference:
            return Response(
                {
                    "detail": "Application / Reference Number is required.",
                    "code": "UDYAM_APPLICATION_REFERENCE_REQUIRED",
                },
                status=400,
            )

        if not submission_date:
            return Response(
                {
                    "detail": "Submission Date is required.",
                    "code": "UDYAM_SUBMISSION_DATE_REQUIRED",
                },
                status=400,
            )

        if not submission_time:
            return Response(
                {
                    "detail": "Submission Time is required.",
                    "code": "UDYAM_SUBMISSION_TIME_REQUIRED",
                },
                status=400,
            )

        next_step = self._udyam_process_step(
            item,
            "APPLICATION_SUBMISSION",
        )

        if next_step is None:
            return Response(
                {
                    "detail": (
                        "Udyam application-submission step is not configured."
                    ),
                    "code": "UDYAM_PROCESS_CONFIGURATION_MISSING",
                },
                status=409,
            )

        with transaction.atomic():
            locked_item = (
                WorkItem.objects
                .select_for_update()
                .get(
                    tenant_id=principal.tenant_id,
                    id=item.id,
                )
            )

            self._locked_udyam_process_state(
                locked_item,
                "SUBMIT_APPLICATION",
            )

            operational_data = dict(
                locked_item.operational_data or {}
            )

            operational_data["udyam_application_reference"] = (
                application_reference
            )
            operational_data["udyam_submission_date"] = (
                submission_date
            )
            operational_data["udyam_submission_time"] = (
                submission_time
            )

            locked_item.operational_data = operational_data
            locked_item.updated_by = principal.principal_id

            locked_item.save(
                update_fields=[
                    "operational_data",
                    "updated_by",
                    "updated_at",
                    "row_version",
                ]
            )

            note = (
                "Udyam application submitted. "
                f"Reference: {application_reference}; "
                f"Submission date: {submission_date}; "
                f"Submission time: {submission_time}; "
                "Stage: Submit Application -> Application Submission."
            )

            self._persist_automated_process_step(
                locked_item,
                next_step,
                principal,
                note,
            )

            self._record(locked_item, note)

        return Response(
            self.get_serializer(locked_item).data,
            status=http_status.HTTP_200_OK,
        )

    @action(
        detail=True,
        methods=["post"],
        url_path="udyam-report-query",
    )
    def udyam_report_query(self, request, pk=None):
        item = self.get_object()
        principal = self._require_udyam_owner(item)

        query_type = str(
            (request.data or {}).get("query_type") or ""
        ).strip()

        remarks = str(
            (request.data or {}).get("remarks") or ""
        ).strip()

        allowed_types = {
            "PORTAL_QUERY",
            "OTP_REQUIRED",
            "TECHNICAL_ISSUE",
            "ADDITIONAL_INFORMATION",
            "DOCUMENT_QUERY",
            "OTHER",
        }

        if query_type not in allowed_types:
            return Response(
                {
                    "detail": "Query / issue type is required.",
                    "code": "UDYAM_QUERY_TYPE_REQUIRED",
                },
                status=400,
            )

        if not remarks:
            return Response(
                {
                    "detail": "Remarks are required.",
                    "code": "UDYAM_QUERY_REMARKS_REQUIRED",
                },
                status=400,
            )

        query_step = self._udyam_process_step(
            item,
            "QUERY_RESOLUTION",
        )

        if query_step is None:
            return Response(
                {
                    "detail": "Udyam query-resolution step is not configured.",
                    "code": "UDYAM_PROCESS_CONFIGURATION_MISSING",
                },
                status=409,
            )

        with transaction.atomic():
            locked_item = (
                WorkItem.objects
                .select_for_update()
                .get(
                    tenant_id=principal.tenant_id,
                    id=item.id,
                )
            )

            self._locked_udyam_process_state(
                locked_item,
                "APPLICATION_SUBMISSION",
            )

            operational_data = dict(
                locked_item.operational_data or {}
            )
            operational_data["udyam_query_type"] = query_type
            operational_data["udyam_query_remarks"] = remarks
            operational_data["udyam_query_resolution_remarks"] = ""
            locked_item.operational_data = operational_data
            locked_item.updated_by = principal.principal_id
            locked_item.save(
                update_fields=["operational_data", "updated_by", "updated_at"]
            )

            note = (
                f"Udyam query / issue reported. "
                f"Type: {query_type}; "
                f"Remarks: {remarks}; "
                "Stage: Application Submission -> Query Resolution."
            )

            self._persist_automated_process_step(
                locked_item,
                query_step,
                principal,
                note,
            )

            self._record(locked_item, note)

        return Response(
            self.get_serializer(locked_item).data,
            status=http_status.HTTP_200_OK,
        )

    @action(
        detail=True,
        methods=["post"],
        url_path="udyam-resolve-query",
    )
    def udyam_resolve_query(self, request, pk=None):
        item = self.get_object()
        principal = self._require_udyam_owner(item)

        remarks = str(
            (request.data or {}).get("remarks") or ""
        ).strip()

        if not remarks:
            return Response(
                {
                    "detail": "Resolution remarks are required.",
                    "code": "UDYAM_RESOLUTION_REMARKS_REQUIRED",
                },
                status=400,
            )

        application_submission_step = self._udyam_process_step(
            item,
            "APPLICATION_SUBMISSION",
        )

        if application_submission_step is None:
            return Response(
                {
                    "detail": (
                        "Udyam application-submission step is not configured."
                    ),
                    "code": "UDYAM_PROCESS_CONFIGURATION_MISSING",
                },
                status=409,
            )

        with transaction.atomic():
            locked_item = (
                WorkItem.objects
                .select_for_update()
                .get(
                    tenant_id=principal.tenant_id,
                    id=item.id,
                )
            )

            self._locked_udyam_process_state(
                locked_item,
                "QUERY_RESOLUTION",
            )

            operational_data = dict(
                locked_item.operational_data or {}
            )
            operational_data["udyam_query_resolution_remarks"] = remarks
            locked_item.operational_data = operational_data
            locked_item.updated_by = principal.principal_id
            locked_item.save(
                update_fields=["operational_data", "updated_by", "updated_at"]
            )

            note = (
                "Udyam query / issue resolved. "
                f"Resolution remarks: {remarks}; "
                "Stage: Query Resolution -> Application Submission."
            )

            self._persist_automated_process_step(
                locked_item,
                application_submission_step,
                principal,
                note,
            )

            self._record(locked_item, note)

        return Response(
            self.get_serializer(locked_item).data,
            status=http_status.HTTP_200_OK,
        )

    @action(
        detail=True,
        methods=["post"],
        parser_classes=[MultiPartParser, FormParser],
        url_path="udyam-complete-registration",
    )
    def udyam_complete_registration(self, request, pk=None):
        item = self.get_object()
        principal = self._require_udyam_owner(item)

        certificate = (
            request.FILES.get("certificate")
            or request.FILES.get("files")
            or request.FILES.get("file")
        )
        remarks = str(
            request.data.get("remarks") or ""
        ).strip()

        if certificate is None:
            return Response(
                {
                    "detail": "Udyam certificate is required.",
                    "code": "UDYAM_CERTIFICATE_REQUIRED",
                },
                status=400,
            )

        completion_step = self._udyam_process_step(
            item,
            "COMPLETION",
        )

        if completion_step is None:
            return Response(
                {
                    "detail": "Udyam completion step is not configured.",
                    "code": "UDYAM_PROCESS_CONFIGURATION_MISSING",
                },
                status=409,
            )

        with transaction.atomic():
            locked_item = (
                WorkItem.objects
                .select_for_update()
                .get(
                    tenant_id=principal.tenant_id,
                    id=item.id,
                )
            )

            self._locked_udyam_process_state(
                locked_item,
                "APPLICATION_SUBMISSION",
            )

            try:
                attachment = _create_attachment(
                    principal=principal,
                    upload=certificate,
                    work_item_id=locked_item.id,
                    source="INTERNAL_TEAM",
                )
            except ValueError as exc:
                return Response(
                    {"detail": str(exc)},
                    status=400,
                )

            operational_data = dict(
                locked_item.operational_data or {}
            )
            operational_data[
                "udyam_certificate_attachment_id"
            ] = str(attachment.id)

            locked_item.operational_data = operational_data
            locked_item.updated_by = principal.principal_id

            locked_item.save(
                update_fields=[
                    "operational_data",
                    "updated_by",
                    "updated_at",
                    "row_version",
                ]
            )

            self._persist_automated_process_step(
                locked_item,
                completion_step,
                principal,
                "Udyam registration completed; certificate received.",
            )

            locked_item.completed_at = timezone.now()

            self._transition(
                locked_item,
                WorkStatus.COMPLETED,
                (
                    remarks
                    or "Udyam registration completed; certificate received."
                ),
                update_fields={"completed_at"},
            )

            note = (
                "Udyam registration completed; certificate received. "
                f"Certificate: {certificate.name}; "
                "Stage: Application Submission -> Completion; "
                "Work completed."
            )

            if remarks:
                note += f" Remarks: {remarks}"

            self._record(locked_item, note)

        response_data = self.get_serializer(
            locked_item
        ).data

        response_data["certificate_attachment"] = (
            DocumentAttachmentSerializer(
                attachment,
                context={"request": request},
            ).data
        )

        return Response(
            response_data,
            status=http_status.HTTP_200_OK,
        )

    # ================================================================
    # MUDRA_LOAN end-to-end runtime (NEW).
    #
    # Mirrors the frozen Udyam runtime patterns (durable WorkProcessState
    # position, backend-authoritative transitions, per-step guard, mandatory
    # audit, WorkNote history) WITHOUT reusing Udyam business states, action
    # names, or completion semantics. All Mudra runtime data is persisted in
    # the existing WorkProcessState (position) and WorkItem.operational_data
    # (service-specific business evidence). No schema change, no new model.
    #
    # System process positions (configuration-owned ServiceProcessStep codes):
    #   APPLICATION -> CREDIT_ELIGIBILITY -> FILE_PREPARATION -> BANK_SUBMITTED
    #   -> BANK_VERIFICATION -> (BANK_PENDING loop) -> RO_REVIEW -> SANCTIONED
    #   -> DISBURSEMENT -> CLOSED, with the eligibility NOT-ELIGIBLE rejected
    #   terminal outcome recorded service-specifically in operational_data.
    # ================================================================

    def _is_mudra_loan(self, item) -> bool:
        """Identify the configured Mudra loan service."""
        if not item.service_id:
            return False
        return Service.objects.filter(
            tenant_id=item.tenant_id,
            id=item.service_id,
            code="MUDRA_LOAN",
        ).exists()

    def _mudra_process_step(self, item, code):
        """Resolve one active configured Mudra process step."""
        if not item.service_id:
            return None
        return (
            ServiceProcessStep.objects
            .filter(
                tenant_id=item.tenant_id,
                service_id=item.service_id,
                code=code,
                is_active=True,
            )
            .first()
        )

    def _require_mudra_owner(self, item):
        principal = self.principal()
        if not self._is_mudra_loan(item):
            raise ValidationError(
                {
                    "detail": "This action is available only for Mudra loan work.",
                    "code": "MUDRA_SERVICE_REQUIRED",
                }
            )
        if not ownership.is_owner(item, principal):
            raise PermissionDenied(
                "Only the assigned owner or a platform administrator "
                "may perform this Mudra action."
            )
        return principal

    def _locked_mudra_process_state(self, item, expected_codes):
        """Lock and assert the Mudra runtime position is one of expected_codes."""
        if isinstance(expected_codes, str):
            expected_codes = (expected_codes,)

        state = (
            WorkProcessState.objects
            .select_for_update()
            .filter(
                tenant_id=item.tenant_id,
                work_item_id=item.id,
            )
            .first()
        )

        expected_ids = {}
        for code in expected_codes:
            step = self._mudra_process_step(item, code)
            if step is None:
                raise ValidationError(
                    {
                        "detail": f"Mudra process step {code} is not configured.",
                        "code": "MUDRA_PROCESS_CONFIGURATION_MISSING",
                    }
                )
            expected_ids[step.id] = code

        if state is None or state.current_step_id not in expected_ids:
            raise ValidationError(
                {
                    "detail": (
                        "This action requires Mudra process step "
                        f"{' or '.join(expected_codes)}."
                    ),
                    "code": "MUDRA_PROCESS_POSITION_REQUIRED",
                }
            )
        return state

    def _mudra_rejected(self, item) -> bool:
        data = item.operational_data or {}
        return str(data.get("mudra_outcome") or "").upper() == "REJECTED"

    def _guard_mudra_not_terminal(self, item):
        """Block any Mudra transition once the case is rejected."""
        if self._mudra_rejected(item):
            raise ValidationError(
                {
                    "detail": "This Mudra case is rejected and is terminal.",
                    "code": "MUDRA_CASE_REJECTED",
                }
            )

    def _mudra_advance(
        self,
        request,
        pk,
        *,
        from_codes,
        to_code,
        fields,
        required,
        note_label,
    ):
        """
        Shared Mudra transition executor.

        Validates required inputs, locks the item, asserts the current position
        is one of from_codes, writes the supplied operational_data fields,
        persists the new WorkProcessState position (+ mandatory audit) and a
        WorkNote, then returns the reconciled Mudra state snapshot.
        """
        item = self.get_object()
        principal = self._require_mudra_owner(item)
        self._guard_mudra_not_terminal(item)

        data = request.data or {}
        values = {}
        for key in fields:
            raw = data.get(key)
            values[key] = "" if raw is None else str(raw).strip()

        for key in required:
            if not values.get(key):
                return Response(
                    {
                        "detail": f"{key} is required for this Mudra action.",
                        "code": "MUDRA_REQUIRED_FIELD_MISSING",
                        "field": key,
                    },
                    status=400,
                )

        next_step = self._mudra_process_step(item, to_code)
        if next_step is None:
            return Response(
                {
                    "detail": f"Mudra process step {to_code} is not configured.",
                    "code": "MUDRA_PROCESS_CONFIGURATION_MISSING",
                },
                status=409,
            )

        with transaction.atomic():
            locked_item = (
                WorkItem.objects
                .select_for_update()
                .get(tenant_id=principal.tenant_id, id=item.id)
            )
            self._locked_mudra_process_state(locked_item, from_codes)

            operational_data = dict(locked_item.operational_data or {})
            for key, val in values.items():
                operational_data[key] = val

            locked_item.operational_data = operational_data
            locked_item.updated_by = principal.principal_id
            locked_item.save(
                update_fields=[
                    "operational_data",
                    "updated_by",
                    "updated_at",
                    "row_version",
                ]
            )

            note = f"Mudra: {note_label} (-> {to_code})."
            self._persist_automated_process_step(
                locked_item, next_step, principal, note,
            )
            self._record(locked_item, note)

        return self._mudra_state_response(locked_item)

    def _mudra_state_response(self, item):
        """Authoritative Mudra snapshot the frontend reconciles against."""
        state = (
            WorkProcessState.objects
            .filter(tenant_id=item.tenant_id, work_item_id=item.id)
            .first()
        )
        current_step = None
        if state is not None and state.current_step_id:
            current_step = (
                ServiceProcessStep.objects
                .filter(
                    tenant_id=item.tenant_id,
                    id=state.current_step_id,
                    service_id=item.service_id,
                    is_active=True,
                )
                .first()
            )
        refreshed = WorkItem.objects.get(tenant_id=item.tenant_id, id=item.id)
        return Response(
            {
                "work_item_id": str(item.id),
                "current_step": (
                    {
                        "id": str(current_step.id),
                        "code": current_step.code,
                        "name": current_step.name,
                        "display_order": current_step.display_order,
                    }
                    if current_step is not None
                    else None
                ),
                "mudra_outcome": str(
                    (refreshed.operational_data or {}).get("mudra_outcome") or ""
                ),
                "work_status": refreshed.status,
                "operational_data": refreshed.operational_data or {},
            },
            status=http_status.HTTP_200_OK,
        )

    # -- Stage 1: Application & KYC - record fields in place (APPLICATION) -
    # CORRECTION: this action no longer advances the Mudra process position.
    # APPLICATION -> CREDIT_ELIGIBILITY is owned exclusively by successful
    # internal reviewer approval (WorkItemViewSet.approve's Mudra branch), so
    # the owner cannot bypass mandatory review by completing this action.
    # The field-recording behavior is preserved unchanged (mirrors
    # mudra_record_cibil's in-place pattern) because the generic
    # OperationalFieldsPanel is disabled once the WorkItem already exists, so
    # this remains the only way to edit these fields before submission.
    @action(detail=True, methods=["post"], url_path="mudra-complete-application")
    def mudra_complete_application(self, request, pk=None):
        item = self.get_object()
        principal = self._require_mudra_owner(item)
        self._guard_mudra_not_terminal(item)

        # Unlike later Mudra stage actions (which are naturally gated by a
        # process position only reachable after review approval), the Mudra
        # process position stays at APPLICATION throughout internal review
        # (Mudra has no configured review-only position for submit_for_review
        # to advance into, unlike Udyam's INTERNAL_REVIEW step). This action
        # must therefore check owner-editable state directly so it cannot be
        # used to edit application data while the case is awaiting or under
        # review - reusing the exact same existing contract the generic Work
        # model already enforces elsewhere, rather than duplicating its state
        # list here.
        if not ownership.can_edit_work_item(item, principal):
            return Response(
                {
                    "detail": (
                        "Application & KYC details can only be recorded "
                        "while this Mudra work item is owner-editable."
                    ),
                    "code": "MUDRA_NOT_OWNER_EDITABLE",
                },
                status=409,
            )

        data = request.data or {}
        fields = [
            "requested_loan_amount", "loan_purpose", "business_activity",
            "application_reference", "application_date",
        ]
        values = {k: ("" if data.get(k) is None else str(data.get(k)).strip())
                  for k in fields}
        for key in ("requested_loan_amount", "loan_purpose"):
            if not values.get(key):
                return Response(
                    {
                        "detail": f"{key} is required for this Mudra action.",
                        "code": "MUDRA_REQUIRED_FIELD_MISSING",
                        "field": key,
                    },
                    status=400,
                )

        with transaction.atomic():
            locked_item = (
                WorkItem.objects
                .select_for_update()
                .get(tenant_id=principal.tenant_id, id=item.id)
            )
            self._locked_mudra_process_state(locked_item, "APPLICATION")
            operational_data = dict(locked_item.operational_data or {})
            for k, v in values.items():
                operational_data[k] = v
            locked_item.operational_data = operational_data
            locked_item.updated_by = principal.principal_id
            locked_item.save(update_fields=[
                "operational_data", "updated_by", "updated_at", "row_version",
            ])
            note = "Mudra: Application & KYC details recorded."
            self._record(locked_item, note)

        return self._mudra_state_response(locked_item)

    # -- Stage 2: record CIBIL (stays in CREDIT_ELIGIBILITY) --------------
    @action(detail=True, methods=["post"], url_path="mudra-record-cibil")
    def mudra_record_cibil(self, request, pk=None):
        item = self.get_object()
        principal = self._require_mudra_owner(item)
        self._guard_mudra_not_terminal(item)

        data = request.data or {}
        fields = [
            "cibil_score", "cibil_bureau", "cibil_check_date",
            "cibil_result", "cibil_report_reference", "cibil_remarks",
        ]
        values = {k: ("" if data.get(k) is None else str(data.get(k)).strip())
                  for k in fields}
        if not values.get("cibil_score"):
            return Response(
                {
                    "detail": "cibil_score is required to record CIBIL.",
                    "code": "MUDRA_REQUIRED_FIELD_MISSING",
                    "field": "cibil_score",
                },
                status=400,
            )

        with transaction.atomic():
            locked_item = (
                WorkItem.objects
                .select_for_update()
                .get(tenant_id=principal.tenant_id, id=item.id)
            )
            self._locked_mudra_process_state(locked_item, "CREDIT_ELIGIBILITY")
            operational_data = dict(locked_item.operational_data or {})
            for k, v in values.items():
                operational_data[k] = v
            locked_item.operational_data = operational_data
            locked_item.updated_by = principal.principal_id
            locked_item.save(update_fields=[
                "operational_data", "updated_by", "updated_at", "row_version",
            ])
            note = f"Mudra: CIBIL recorded (score {values['cibil_score']})."
            self._record(locked_item, note)

        return self._mudra_state_response(locked_item)

    # -- Stage 2: eligibility decision -> continue OR reject --------------
    @action(detail=True, methods=["post"], url_path="mudra-decide-eligibility")
    def mudra_decide_eligibility(self, request, pk=None):
        item = self.get_object()
        principal = self._require_mudra_owner(item)
        self._guard_mudra_not_terminal(item)

        data = request.data or {}
        decision = str(data.get("eligibility_result") or "").strip().upper()
        eligibility_date = str(data.get("eligibility_date") or "").strip()
        rejection_reason = str(data.get("rejection_reason") or "").strip()

        if decision not in {"ELIGIBLE", "NOT_ELIGIBLE"}:
            return Response(
                {
                    "detail": "eligibility_result must be ELIGIBLE or NOT_ELIGIBLE.",
                    "code": "MUDRA_ELIGIBILITY_RESULT_INVALID",
                },
                status=400,
            )
        if decision == "NOT_ELIGIBLE" and not rejection_reason:
            return Response(
                {
                    "detail": "rejection_reason is required when NOT_ELIGIBLE.",
                    "code": "MUDRA_REJECTION_REASON_REQUIRED",
                    "field": "rejection_reason",
                },
                status=400,
            )

        with transaction.atomic():
            locked_item = (
                WorkItem.objects
                .select_for_update()
                .get(tenant_id=principal.tenant_id, id=item.id)
            )
            self._locked_mudra_process_state(locked_item, "CREDIT_ELIGIBILITY")
            operational_data = dict(locked_item.operational_data or {})
            operational_data["eligibility_result"] = decision
            operational_data["eligibility_date"] = eligibility_date

            if decision == "NOT_ELIGIBLE":
                # Durable, service-specific rejected terminal outcome. Generic
                # WorkStatus is NOT changed to add a Mudra-specific enum value.
                operational_data["rejection_reason"] = rejection_reason
                operational_data["mudra_outcome"] = "REJECTED"
                locked_item.operational_data = operational_data
                locked_item.updated_by = principal.principal_id
                locked_item.save(update_fields=[
                    "operational_data", "updated_by", "updated_at", "row_version",
                ])
                note = (
                    "Mudra: eligibility decided NOT ELIGIBLE; case rejected "
                    f"(terminal). Reason: {rejection_reason}."
                )
                # Keep the durable position at CREDIT_ELIGIBILITY; the rejected
                # outcome flag makes the case terminal and blocks advancement.
                self._record(locked_item, note)
                try:
                    record_event(
                        tenant_id=principal.tenant_id,
                        principal_id=principal.principal_id,
                        action=AuditAction.STATUS_CHANGE,
                        entity_type="WorkItem",
                        entity_id=locked_item.id,
                        summary="Mudra eligibility: NOT ELIGIBLE -> REJECTED",
                        previous={"mudra_outcome": ""},
                        new={"mudra_outcome": "REJECTED"},
                        request=self.request,
                    )
                except Exception as exc:
                    raise MandatoryAuditPersistenceError() from exc
                return self._mudra_state_response(locked_item)

            # ELIGIBLE -> advance to FILE_PREPARATION
            next_step = self._mudra_process_step(locked_item, "FILE_PREPARATION")
            if next_step is None:
                return Response(
                    {
                        "detail": "Mudra FILE_PREPARATION step is not configured.",
                        "code": "MUDRA_PROCESS_CONFIGURATION_MISSING",
                    },
                    status=409,
                )
            locked_item.operational_data = operational_data
            locked_item.updated_by = principal.principal_id
            locked_item.save(update_fields=[
                "operational_data", "updated_by", "updated_at", "row_version",
            ])
            note = "Mudra: eligibility decided ELIGIBLE (-> FILE_PREPARATION)."
            self._persist_automated_process_step(
                locked_item, next_step, principal, note,
            )
            self._record(locked_item, note)

        return self._mudra_state_response(locked_item)

    # -- Stage 3 -> 4: project report complete ---------------------------
    @action(detail=True, methods=["post"], url_path="mudra-complete-file-preparation")
    def mudra_complete_file_preparation(self, request, pk=None):
        return self._mudra_advance(
            request, pk,
            from_codes="FILE_PREPARATION",
            to_code="BANK_SUBMITTED",
            fields=["project_report_prepared", "project_report_date"],
            required=["project_report_prepared"],
            note_label="File preparation (project report) completed",
        )

    # -- Stage 4 -> 5: bank submitted (transfer + acknowledgement) --------
    @action(detail=True, methods=["post"], url_path="mudra-record-bank-submission")
    def mudra_record_bank_submission(self, request, pk=None):
        return self._mudra_advance(
            request, pk,
            from_codes="BANK_SUBMITTED",
            to_code="BANK_VERIFICATION",
            fields=[
                "bank_name", "bank_branch", "bank_file_transfer_date",
                "bank_reference", "bank_acknowledgement_date",
            ],
            required=["bank_name", "bank_acknowledgement_date"],
            note_label="Bank file transferred and acknowledgement recorded",
        )

    # -- Stage 5: bank verification -> CLEAR (RO_REVIEW) or PENDING -------
    @action(detail=True, methods=["post"], url_path="mudra-record-bank-verification")
    def mudra_record_bank_verification(self, request, pk=None):
        item = self.get_object()
        principal = self._require_mudra_owner(item)
        self._guard_mudra_not_terminal(item)

        data = request.data or {}
        outcome = str(data.get("bank_verification_status") or "").strip().upper()
        verification_date = str(data.get("bank_verification_date") or "").strip()
        remarks = str(data.get("bank_verification_remarks") or "").strip()

        if outcome not in {"CLEAR", "PENDING"}:
            return Response(
                {
                    "detail": "bank_verification_status must be CLEAR or PENDING.",
                    "code": "MUDRA_BANK_VERIFICATION_STATUS_INVALID",
                },
                status=400,
            )

        to_code = "RO_REVIEW" if outcome == "CLEAR" else "BANK_PENDING"
        next_step = self._mudra_process_step(item, to_code)
        if next_step is None:
            return Response(
                {
                    "detail": f"Mudra process step {to_code} is not configured.",
                    "code": "MUDRA_PROCESS_CONFIGURATION_MISSING",
                },
                status=409,
            )

        with transaction.atomic():
            locked_item = (
                WorkItem.objects
                .select_for_update()
                .get(tenant_id=principal.tenant_id, id=item.id)
            )
            # Verification is decided from BANK_VERIFICATION only (after Re-QC
            # the case returns here and the decision is made again).
            self._locked_mudra_process_state(locked_item, "BANK_VERIFICATION")
            operational_data = dict(locked_item.operational_data or {})
            operational_data["bank_verification_status"] = outcome
            operational_data["bank_verification_date"] = verification_date
            operational_data["bank_verification_remarks"] = remarks
            locked_item.operational_data = operational_data
            locked_item.updated_by = principal.principal_id
            locked_item.save(update_fields=[
                "operational_data", "updated_by", "updated_at", "row_version",
            ])
            note = f"Mudra: bank verification {outcome} (-> {to_code})."
            self._persist_automated_process_step(
                locked_item, next_step, principal, note,
            )
            self._record(locked_item, note)

        return self._mudra_state_response(locked_item)

    # -- Stage 6: BANK_PENDING - raise/assign a pending requirement -------
    @action(detail=True, methods=["post"], url_path="mudra-raise-pending-task")
    def mudra_raise_pending_task(self, request, pk=None):
        item = self.get_object()
        principal = self._require_mudra_owner(item)
        self._guard_mudra_not_terminal(item)

        data = request.data or {}
        reason = str(data.get("pending_reason") or "").strip()
        requested_info = str(data.get("pending_requested_info") or "").strip()
        assignee = str(data.get("pending_assignee_user_id") or "").strip()

        if not reason:
            return Response(
                {
                    "detail": "pending_reason is required to raise a pending task.",
                    "code": "MUDRA_REQUIRED_FIELD_MISSING",
                    "field": "pending_reason",
                },
                status=400,
            )

        with transaction.atomic():
            locked_item = (
                WorkItem.objects
                .select_for_update()
                .get(tenant_id=principal.tenant_id, id=item.id)
            )
            self._locked_mudra_process_state(locked_item, "BANK_PENDING")
            operational_data = dict(locked_item.operational_data or {})
            # Single active pending task (durable, service-specific).
            pending = {
                "status": "OPEN",
                "reason": reason,
                "requested_info": requested_info,
                "assignee_user_id": assignee,
                "evidence": "",
                "reqc_status": "",
                "raised_by": str(principal.principal_id),
            }
            operational_data["mudra_pending_task"] = pending
            locked_item.operational_data = operational_data
            locked_item.updated_by = principal.principal_id
            locked_item.save(update_fields=[
                "operational_data", "updated_by", "updated_at", "row_version",
            ])
            note = f"Mudra: pending task raised. Reason: {reason}."
            if assignee:
                note += f" Assigned to: {assignee}."
            self._record(locked_item, note)

        return self._mudra_state_response(locked_item)

    # -- Stage 6: BANK_PENDING - reassign the pending requirement ---------
    @action(detail=True, methods=["post"], url_path="mudra-reassign-pending-task")
    def mudra_reassign_pending_task(self, request, pk=None):
        item = self.get_object()
        principal = self._require_mudra_owner(item)
        self._guard_mudra_not_terminal(item)

        data = request.data or {}
        assignee = str(data.get("pending_assignee_user_id") or "").strip()
        if not assignee:
            return Response(
                {
                    "detail": "pending_assignee_user_id is required to reassign.",
                    "code": "MUDRA_REQUIRED_FIELD_MISSING",
                    "field": "pending_assignee_user_id",
                },
                status=400,
            )

        with transaction.atomic():
            locked_item = (
                WorkItem.objects
                .select_for_update()
                .get(tenant_id=principal.tenant_id, id=item.id)
            )
            self._locked_mudra_process_state(locked_item, "BANK_PENDING")
            operational_data = dict(locked_item.operational_data or {})
            pending = dict(operational_data.get("mudra_pending_task") or {})
            if not pending or pending.get("status") not in {"OPEN", "RECEIVED"}:
                return Response(
                    {
                        "detail": "No active pending task to reassign.",
                        "code": "MUDRA_NO_ACTIVE_PENDING_TASK",
                    },
                    status=409,
                )
            previous = pending.get("assignee_user_id") or ""
            pending["assignee_user_id"] = assignee
            operational_data["mudra_pending_task"] = pending
            locked_item.operational_data = operational_data
            locked_item.updated_by = principal.principal_id
            locked_item.save(update_fields=[
                "operational_data", "updated_by", "updated_at", "row_version",
            ])
            note = f"Mudra: pending task reassigned {previous or 'NONE'} -> {assignee}."
            self._record(locked_item, note)

        return self._mudra_state_response(locked_item)

    # -- Stage 6: BANK_PENDING - record evidence/information received -----
    @action(detail=True, methods=["post"], url_path="mudra-record-pending-evidence")
    def mudra_record_pending_evidence(self, request, pk=None):
        item = self.get_object()
        principal = self._require_mudra_owner(item)
        self._guard_mudra_not_terminal(item)

        data = request.data or {}
        evidence = str(data.get("pending_evidence") or "").strip()
        if not evidence:
            return Response(
                {
                    "detail": "pending_evidence is required.",
                    "code": "MUDRA_REQUIRED_FIELD_MISSING",
                    "field": "pending_evidence",
                },
                status=400,
            )

        with transaction.atomic():
            locked_item = (
                WorkItem.objects
                .select_for_update()
                .get(tenant_id=principal.tenant_id, id=item.id)
            )
            self._locked_mudra_process_state(locked_item, "BANK_PENDING")
            operational_data = dict(locked_item.operational_data or {})
            pending = dict(operational_data.get("mudra_pending_task") or {})
            if not pending or pending.get("status") not in {"OPEN", "RECEIVED"}:
                return Response(
                    {
                        "detail": "No active pending task to record evidence against.",
                        "code": "MUDRA_NO_ACTIVE_PENDING_TASK",
                    },
                    status=409,
                )
            pending["evidence"] = evidence
            pending["status"] = "RECEIVED"
            operational_data["mudra_pending_task"] = pending
            locked_item.operational_data = operational_data
            locked_item.updated_by = principal.principal_id
            locked_item.save(update_fields=[
                "operational_data", "updated_by", "updated_at", "row_version",
            ])
            note = "Mudra: pending task information/evidence received."
            self._record(locked_item, note)

        return self._mudra_state_response(locked_item)

    # -- Stage 6 -> 5: BANK_PENDING Re-QC returns to BANK_VERIFICATION ----
    @action(detail=True, methods=["post"], url_path="mudra-complete-reqc")
    def mudra_complete_reqc(self, request, pk=None):
        item = self.get_object()
        principal = self._require_mudra_owner(item)
        self._guard_mudra_not_terminal(item)

        next_step = self._mudra_process_step(item, "BANK_VERIFICATION")
        if next_step is None:
            return Response(
                {
                    "detail": "Mudra BANK_VERIFICATION step is not configured.",
                    "code": "MUDRA_PROCESS_CONFIGURATION_MISSING",
                },
                status=409,
            )

        with transaction.atomic():
            locked_item = (
                WorkItem.objects
                .select_for_update()
                .get(tenant_id=principal.tenant_id, id=item.id)
            )
            self._locked_mudra_process_state(locked_item, "BANK_PENDING")
            operational_data = dict(locked_item.operational_data or {})
            pending = dict(operational_data.get("mudra_pending_task") or {})
            if not pending or pending.get("status") != "RECEIVED":
                return Response(
                    {
                        "detail": (
                            "Re-QC requires an active pending task with "
                            "received information."
                        ),
                        "code": "MUDRA_PENDING_EVIDENCE_REQUIRED",
                    },
                    status=409,
                )
            # Close the pending task after Re-QC and return to verification.
            pending["status"] = "RESOLVED"
            pending["reqc_status"] = "COMPLETE"
            operational_data["mudra_pending_task"] = pending
            # Clear the prior verification decision so verification is made again.
            operational_data["bank_verification_status"] = ""
            locked_item.operational_data = operational_data
            locked_item.updated_by = principal.principal_id
            locked_item.save(update_fields=[
                "operational_data", "updated_by", "updated_at", "row_version",
            ])
            note = (
                "Mudra: Re-QC complete; pending task resolved "
                "(-> BANK_VERIFICATION)."
            )
            self._persist_automated_process_step(
                locked_item, next_step, principal, note,
            )
            self._record(locked_item, note)

        return self._mudra_state_response(locked_item)

    # -- Stage 7 -> 8: RO review complete --------------------------------
    @action(detail=True, methods=["post"], url_path="mudra-complete-ro-review")
    def mudra_complete_ro_review(self, request, pk=None):
        return self._mudra_advance(
            request, pk,
            from_codes="RO_REVIEW",
            to_code="SANCTIONED",
            fields=[
                "ro_name", "ro_review_status", "ro_review_date", "ro_review_remarks",
            ],
            required=["ro_review_status"],
            note_label="RO review completed",
        )

    # -- Stage 8: record sanction (stays in SANCTIONED) ------------------
    @action(detail=True, methods=["post"], url_path="mudra-record-sanction")
    def mudra_record_sanction(self, request, pk=None):
        item = self.get_object()
        principal = self._require_mudra_owner(item)
        self._guard_mudra_not_terminal(item)

        data = request.data or {}
        fields = [
            "sanctioned_amount", "sanction_date",
            "sanction_reference", "sanction_remarks",
        ]
        values = {k: ("" if data.get(k) is None else str(data.get(k)).strip())
                  for k in fields}
        if not values.get("sanctioned_amount"):
            return Response(
                {
                    "detail": "sanctioned_amount is required to record sanction.",
                    "code": "MUDRA_REQUIRED_FIELD_MISSING",
                    "field": "sanctioned_amount",
                },
                status=400,
            )

        with transaction.atomic():
            locked_item = (
                WorkItem.objects
                .select_for_update()
                .get(tenant_id=principal.tenant_id, id=item.id)
            )
            self._locked_mudra_process_state(locked_item, "SANCTIONED")
            operational_data = dict(locked_item.operational_data or {})
            for k, v in values.items():
                operational_data[k] = v
            locked_item.operational_data = operational_data
            locked_item.updated_by = principal.principal_id
            locked_item.save(update_fields=[
                "operational_data", "updated_by", "updated_at", "row_version",
            ])
            note = f"Mudra: sanction recorded (amount {values['sanctioned_amount']})."
            self._record(locked_item, note)

        return self._mudra_state_response(locked_item)

    # -- Stage 8 -> 9: sanction conditions complete ----------------------
    @action(detail=True, methods=["post"], url_path="mudra-complete-sanction-conditions")
    def mudra_complete_sanction_conditions(self, request, pk=None):
        item = self.get_object()
        principal = self._require_mudra_owner(item)
        self._guard_mudra_not_terminal(item)

        data = request.data or {}
        status_val = str(data.get("sanction_conditions_status") or "").strip().upper()
        completed_date = str(
            data.get("sanction_conditions_completed_date") or ""
        ).strip()

        # Do not advance to DISBURSEMENT unless conditions are satisfied. A
        # sanction must have been recorded first (sanctioned_amount present).
        existing = self.get_object().operational_data or {}
        if not str(existing.get("sanctioned_amount") or "").strip():
            return Response(
                {
                    "detail": "Record sanction before completing sanction conditions.",
                    "code": "MUDRA_SANCTION_REQUIRED_FIRST",
                },
                status=409,
            )
        if status_val != "COMPLETE":
            return Response(
                {
                    "detail": (
                        "sanction_conditions_status must be COMPLETE to advance "
                        "to disbursement."
                    ),
                    "code": "MUDRA_SANCTION_CONDITIONS_INCOMPLETE",
                },
                status=400,
            )

        next_step = self._mudra_process_step(item, "DISBURSEMENT")
        if next_step is None:
            return Response(
                {
                    "detail": "Mudra DISBURSEMENT step is not configured.",
                    "code": "MUDRA_PROCESS_CONFIGURATION_MISSING",
                },
                status=409,
            )

        with transaction.atomic():
            locked_item = (
                WorkItem.objects
                .select_for_update()
                .get(tenant_id=principal.tenant_id, id=item.id)
            )
            self._locked_mudra_process_state(locked_item, "SANCTIONED")
            operational_data = dict(locked_item.operational_data or {})
            operational_data["sanction_conditions_status"] = "COMPLETE"
            operational_data["sanction_conditions_completed_date"] = completed_date
            locked_item.operational_data = operational_data
            locked_item.updated_by = principal.principal_id
            locked_item.save(update_fields=[
                "operational_data", "updated_by", "updated_at", "row_version",
            ])
            note = "Mudra: sanction conditions complete (-> DISBURSEMENT)."
            self._persist_automated_process_step(
                locked_item, next_step, principal, note,
            )
            self._record(locked_item, note)

        return self._mudra_state_response(locked_item)

    # -- Stage 9: mark disbursement ready (stays in DISBURSEMENT) --------
    @action(detail=True, methods=["post"], url_path="mudra-mark-disbursement-ready")
    def mudra_mark_disbursement_ready(self, request, pk=None):
        item = self.get_object()
        principal = self._require_mudra_owner(item)
        self._guard_mudra_not_terminal(item)

        data = request.data or {}
        ready_date = str(data.get("disbursement_ready_date") or "").strip()
        if not ready_date:
            return Response(
                {
                    "detail": "disbursement_ready_date is required.",
                    "code": "MUDRA_REQUIRED_FIELD_MISSING",
                    "field": "disbursement_ready_date",
                },
                status=400,
            )

        with transaction.atomic():
            locked_item = (
                WorkItem.objects
                .select_for_update()
                .get(tenant_id=principal.tenant_id, id=item.id)
            )
            self._locked_mudra_process_state(locked_item, "DISBURSEMENT")
            operational_data = dict(locked_item.operational_data or {})
            operational_data["disbursement_ready_date"] = ready_date
            operational_data["mudra_disbursement_ready"] = "YES"
            locked_item.operational_data = operational_data
            locked_item.updated_by = principal.principal_id
            locked_item.save(update_fields=[
                "operational_data", "updated_by", "updated_at", "row_version",
            ])
            note = "Mudra: disbursement marked ready."
            self._record(locked_item, note)

        return self._mudra_state_response(locked_item)

    # -- Stage 9 -> 10: record actual disbursement and close -------------
    @action(detail=True, methods=["post"], url_path="mudra-record-disbursement")
    def mudra_record_disbursement(self, request, pk=None):
        item = self.get_object()
        principal = self._require_mudra_owner(item)
        self._guard_mudra_not_terminal(item)

        data = request.data or {}
        fields = ["disbursed_amount", "disbursement_date", "disbursement_reference"]
        values = {k: ("" if data.get(k) is None else str(data.get(k)).strip())
                  for k in fields}
        if not values.get("disbursed_amount") or not values.get("disbursement_date"):
            return Response(
                {
                    "detail": (
                        "disbursed_amount and disbursement_date are required "
                        "to record actual disbursement."
                    ),
                    "code": "MUDRA_REQUIRED_FIELD_MISSING",
                },
                status=400,
            )

        existing = self.get_object().operational_data or {}
        if str(existing.get("mudra_disbursement_ready") or "") != "YES":
            return Response(
                {
                    "detail": "Mark disbursement ready before recording disbursement.",
                    "code": "MUDRA_DISBURSEMENT_NOT_READY",
                },
                status=409,
            )

        closed_step = self._mudra_process_step(item, "CLOSED")
        if closed_step is None:
            return Response(
                {
                    "detail": "Mudra CLOSED step is not configured.",
                    "code": "MUDRA_PROCESS_CONFIGURATION_MISSING",
                },
                status=409,
            )

        with transaction.atomic():
            locked_item = (
                WorkItem.objects
                .select_for_update()
                .get(tenant_id=principal.tenant_id, id=item.id)
            )
            self._locked_mudra_process_state(locked_item, "DISBURSEMENT")
            operational_data = dict(locked_item.operational_data or {})
            for k, v in values.items():
                operational_data[k] = v
            operational_data["mudra_outcome"] = "CLOSED"
            operational_data["closure_date"] = (
                values["disbursement_date"] or str(timezone.now().date())
            )
            locked_item.operational_data = operational_data
            locked_item.updated_by = principal.principal_id
            locked_item.save(update_fields=[
                "operational_data", "updated_by", "updated_at", "row_version",
            ])
            note = (
                "Mudra: disbursement recorded "
                f"(amount {values['disbursed_amount']}); case closed (-> CLOSED)."
            )
            self._persist_automated_process_step(
                locked_item, closed_step, principal, note,
            )

            # Reuse the existing shared WorkItem completion mechanism (the same
            # frozen _transition helper the Udyam completion action uses) so
            # WorkItem.status becomes COMPLETED, completed_at is persisted, and
            # the mandatory audit + WorkNote are written through the one
            # authoritative path. Previously this action only recorded the
            # Mudra-specific CLOSED outcome in operational_data and left
            # WorkItem.status unchanged. _transition itself is not modified.
            locked_item.completed_at = timezone.now()
            self._transition(
                locked_item,
                WorkStatus.COMPLETED,
                note,
                update_fields={"completed_at"},
            )

        return self._mudra_state_response(locked_item)

    # -- Read-only authoritative Mudra snapshot --------------------------
    @action(detail=True, methods=["get"], url_path="mudra-state")
    def mudra_state(self, request, pk=None):
        item = self.get_object()
        self.principal()
        if not self._is_mudra_loan(item):
            return Response(
                {
                    "detail": "This work item is not a Mudra loan.",
                    "code": "MUDRA_SERVICE_REQUIRED",
                },
                status=400,
            )
        return self._mudra_state_response(item)


    # -- generic guarded transition (cannot complete review-required) --
    @action(detail=True, methods=["post"])
    def set_status(self, request, pk=None):
        item = self.get_object()
        target = request.data.get("status")
        comment = request.data.get("comment", "")
        # 1. Structural transition validation first, so invalid transitions keep
        #    their existing 400 contract rather than being masked by a 403.
        valid = {c.value for c in WorkStatus}
        if target not in valid:
            return Response({"detail": "Unknown status."}, status=400)
        if target == item.status:
            return Response(self.get_serializer(item).data)
        allowed = {s.value for s in _ALLOWED_TRANSITIONS[WorkStatus(item.status)]}
        if target not in allowed:
            return Response(
                {"detail": f"Cannot move from {item.status} to {target} here."}, status=400
            )
        # 2. For a structurally valid transition from an editable source state,
        #    enforce C4 owner control.
        if not ownership.is_owner(item, self.principal()):
            raise PermissionDenied(
                "Only the assigned owner may change the status of this work item here."
            )
        if target == WorkStatus.REWORK_REQUIRED and not comment:
            return Response({"detail": "A comment is required to return work for rework."}, status=400)
        update_fields = set()
        if target in (WorkStatus.IN_PROGRESS, WorkStatus.REWORK_REQUIRED):
            item.completed_at = None
            update_fields.add("completed_at")
        if target == WorkStatus.READY_FOR_REVIEW:
            item.submitted_for_review_at = timezone.now()
            update_fields.add("submitted_for_review_at")
        self._transition(item, target, comment, update_fields=update_fields)
        return Response(self.get_serializer(item).data)

    # -- explicit review verbs -----------------------------------------
    @action(
        detail=True,
        methods=["post"],
        url_path="prepare-qa",
    )
    def prepare_qa(self, request, pk=None):
        item = self.get_object()
        if not ownership.is_owner(item, self.principal()):
            raise PermissionDenied(
                "Only the assigned owner may prepare the QA checklist."
            )
        try:
            cycle = qa_prepare_cycle(item, self.principal())
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=400)
        return Response(
            {
                "qa_enabled": cycle is not None,
                "cycle": qa_cycle_summary(cycle),
                "qa_readiness": qa_readiness(item),
            }
        )

    @action(
        detail=True,
        methods=["get"],
        url_path="qa-readiness",
    )
    def qa_readiness_action(self, request, pk=None):
        item = self.get_object()
        return Response(qa_readiness(item))

    @action(
        detail=True,
        methods=["get"],
        url_path="qa-review-history",
    )
    def qa_review_history_action(self, request, pk=None):
        item = self.get_object()
        return Response(qa_review_history(item))

    @action(
        detail=True,
        methods=["post"],
        url_path="save-preparer-checklist",
    )
    def save_preparer_checklist(self, request, pk=None):
        item = self.get_object()
        if not ownership.is_owner(item, self.principal()):
            raise PermissionDenied(
                "Only the assigned owner may complete the preparer checklist."
            )
        try:
            cycle = qa_save_responses(
                item,
                self.principal(),
                request.data or {},
                role="preparer",
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=400)
        return Response(
            {
                "cycle": qa_cycle_summary(cycle),
                "qa_readiness": qa_readiness(item),
            }
        )

    @action(
        detail=True,
        methods=["post"],
        url_path="save-reviewer-checklist",
    )
    def save_reviewer_checklist(self, request, pk=None):
        item = self.get_object()
        self._require_reviewer(item)
        try:
            cycle = qa_save_responses(
                item,
                self.principal(),
                request.data or {},
                role="reviewer",
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=400)
        return Response(
            {
                "cycle": qa_cycle_summary(cycle),
                "qa_readiness": qa_readiness(item),
            }
        )

    @action(
        detail=True,
        methods=["post"],
        url_path="raise-qa-issue",
    )
    def raise_qa_issue_action(self, request, pk=None):
        item = self.get_object()
        self._require_reviewer(item)
        try:
            issue = qa_raise_issue(
                item,
                self.principal(),
                request.data or {},
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=400)
        return Response(
            {
                "issue_id": str(issue.id),
                "qa_readiness": qa_readiness(item),
            },
            status=201,
        )

    @action(
        detail=True,
        methods=["post"],
        url_path="resolve-qa-issue",
    )
    def resolve_qa_issue_action(self, request, pk=None):
        item = self.get_object()
        if not ownership.is_owner(item, self.principal()):
            raise PermissionDenied(
                "Only the assigned owner may resolve a QA correction."
            )
        try:
            issue = qa_resolve_issue(
                item,
                self.principal(),
                (request.data or {}).get("issue_id"),
                (request.data or {}).get("comment"),
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=400)
        return Response(
            {
                "issue_id": str(issue.id),
                "status": issue.status,
                "qa_readiness": qa_readiness(item),
            }
        )

    @action(
        detail=True,
        methods=["get"],
        url_path="health",
    )
    def health(self, request, pk=None):
        item = self.get_object()
        health = calculate_work_health(item)

        # Work Health remains generic. A durable Udyam business-process
        # position refines only the service-specific next action.
        if (
            item.status == WorkStatus.IN_PROGRESS
            and self._is_udyam_registration(item)
        ):
            process_state = (
                WorkProcessState.objects
                .filter(
                    tenant_id=self.principal().tenant_id,
                    work_item_id=item.id,
                )
                .first()
            )

            if (
                process_state is not None
                and process_state.current_step_id
            ):
                current_step = (
                    ServiceProcessStep.objects
                    .filter(
                        tenant_id=self.principal().tenant_id,
                        service_id=item.service_id,
                        id=process_state.current_step_id,
                        is_active=True,
                    )
                    .first()
                )

                if current_step is not None:
                    if current_step.code == "SUBMIT_APPLICATION":
                        health["next_action"] = {
                            "code": "SUBMIT_UDYAM_APPLICATION",
                            "label": "Submit Udyam application",
                        }
                    elif current_step.code == "APPLICATION_SUBMISSION":
                        health["next_action"] = {
                            "code": "AWAIT_UDYAM_OUTCOME",
                            "label": "Await registration outcome",
                        }
                    elif current_step.code == "QUERY_RESOLUTION":
                        health["next_action"] = {
                            "code": "RESOLVE_UDYAM_QUERY",
                            "label": "Resolve query / OTP / technical issue",
                        }
                    elif current_step.code == "COMPLETION":
                        # Registration completion is terminal.
                        #
                        # Do not expose the pre-completion
                        # AWAIT_UDYAM_OUTCOME action after the
                        # durable process position has reached
                        # COMPLETION.
                        health["next_action"] = {
                            "code": "NONE",
                            "label": "Work completed",
                        }

        # Work Health remains generic. A durable Mudra business-process
        # position refines only the service-specific next action -
        # mirroring the Udyam block above exactly. Once the one-time
        # initial internal review is complete (current_step != APPLICATION),
        # the generic SUBMIT_FOR_REVIEW recommendation is no longer valid:
        # review has already happened, and re-submitting is blocked
        # elsewhere (MUDRA_INTERNAL_REVIEW_ALREADY_COMPLETED). CLOSED is not
        # handled here because calculate_work_health already returns the
        # correct terminal NONE/"Work completed" action once
        # WorkItem.status reaches COMPLETED (Mudra's true terminal state),
        # before this override would even run.
        elif (
            item.status == WorkStatus.IN_PROGRESS
            and self._is_mudra_loan(item)
        ):
            process_state = (
                WorkProcessState.objects
                .filter(
                    tenant_id=self.principal().tenant_id,
                    work_item_id=item.id,
                )
                .first()
            )

            if (
                process_state is not None
                and process_state.current_step_id
            ):
                current_step = (
                    ServiceProcessStep.objects
                    .filter(
                        tenant_id=self.principal().tenant_id,
                        service_id=item.service_id,
                        id=process_state.current_step_id,
                        is_active=True,
                    )
                    .first()
                )

                if current_step is not None:
                    if current_step.code == "CREDIT_ELIGIBILITY":
                        health["next_action"] = {
                            "code": "CONTINUE_MUDRA_CREDIT_ELIGIBILITY",
                            "label": "Complete Credit & Eligibility",
                        }
                    elif current_step.code == "FILE_PREPARATION":
                        health["next_action"] = {
                            "code": "CONTINUE_MUDRA_FILE_PREPARATION",
                            "label": "Complete File Preparation",
                        }
                    elif current_step.code == "BANK_SUBMITTED":
                        health["next_action"] = {
                            "code": "CONTINUE_MUDRA_BANK_SUBMITTED",
                            "label": "Record Bank Submission",
                        }
                    elif current_step.code == "BANK_VERIFICATION":
                        health["next_action"] = {
                            "code": "CONTINUE_MUDRA_BANK_VERIFICATION",
                            "label": "Record Bank Verification",
                        }
                    elif current_step.code == "BANK_PENDING":
                        health["next_action"] = {
                            "code": "RESOLVE_MUDRA_BANK_PENDING",
                            "label": "Resolve Bank Pending Item",
                        }
                    elif current_step.code == "RO_REVIEW":
                        health["next_action"] = {
                            "code": "CONTINUE_MUDRA_RO_REVIEW",
                            "label": "Complete RO Review",
                        }
                    elif current_step.code == "SANCTIONED":
                        health["next_action"] = {
                            "code": "CONTINUE_MUDRA_SANCTION",
                            "label": "Complete Sanction Process",
                        }
                    elif current_step.code == "DISBURSEMENT":
                        health["next_action"] = {
                            "code": "CONTINUE_MUDRA_DISBURSEMENT",
                            "label": "Record Disbursement",
                        }
                    # current_step.code == "APPLICATION" intentionally falls
                    # through with no override: before the one-time initial
                    # internal review, generic SUBMIT_FOR_REVIEW remains the
                    # correct recommendation.

        return Response(
            health,
            status=http_status.HTTP_200_OK,
        )

    @action(
        detail=True,
        methods=["get"],
        url_path="document-readiness",
    )
    def document_readiness(self, request, pk=None):
        item = self.get_object()

        return Response(
            calculate_document_readiness(item)
        )

    @action(detail=True, methods=["post"])
    def submit_for_review(self, request, pk=None):
        item = self.get_object()

        if not ownership.is_owner(item, self.principal()):
            raise PermissionDenied(
                "Only the assigned owner may submit this work "
                "for review."
            )

        if item.status != WorkStatus.IN_PROGRESS:
            return Response(
                {
                    "detail": (
                        "Only work in progress can be submitted "
                        "for review."
                    )
                },
                status=400,
            )

        readiness = calculate_document_readiness(item)
        if not readiness["ready_for_review"]:
            return Response(
                {
                    "detail": (
                        "Mandatory document dependencies are not "
                        "satisfied."
                    ),
                    "code": "DOCUMENT_DEPENDENCIES_BLOCKED",
                    "document_readiness": readiness,
                },
                status=400,
            )

        udyam_internal_review_step = None

        if self._is_udyam_registration(item):
            udyam_internal_review_step = self._udyam_process_step(
                item,
                "INTERNAL_REVIEW",
            )

            if udyam_internal_review_step is None:
                return Response(
                    {
                        "detail": (
                            "Udyam Internal Review process configuration "
                            "is unavailable."
                        ),
                        "code": "UDYAM_PROCESS_CONFIGURATION_MISSING",
                    },
                    status=409,
                )

            existing_state = (
                WorkProcessState.objects
                .filter(
                    tenant_id=self.principal().tenant_id,
                    work_item_id=item.id,
                )
                .first()
            )

            if existing_state is not None and existing_state.current_step_id:
                existing_step = (
                    ServiceProcessStep.objects
                    .filter(
                        tenant_id=self.principal().tenant_id,
                        service_id=item.service_id,
                        id=existing_state.current_step_id,
                        is_active=True,
                    )
                    .first()
                )

                if (
                    existing_step is not None
                    and int(existing_step.display_order or 0) >= 40
                ):
                    return Response(
                        {
                            "detail": (
                                "Internal review has already been completed "
                                "for this Udyam work item."
                            ),
                            "code": (
                                "UDYAM_INTERNAL_REVIEW_ALREADY_COMPLETED"
                            ),
                        },
                        status=409,
                    )

        elif self._is_mudra_loan(item):
            # Mudra correction: once initial internal review has already been
            # completed (the durable position has moved past APPLICATION),
            # submitting for review again would let the owner re-enter the
            # review gate mid-lifecycle - a Work status / process position
            # inconsistency the corrected architecture must not allow.
            mudra_application_step = self._mudra_process_step(
                item,
                "APPLICATION",
            )

            if mudra_application_step is not None:
                existing_state = (
                    WorkProcessState.objects
                    .filter(
                        tenant_id=self.principal().tenant_id,
                        work_item_id=item.id,
                    )
                    .first()
                )

                if (
                    existing_state is not None
                    and existing_state.current_step_id
                    and existing_state.current_step_id
                    != mudra_application_step.id
                ):
                    return Response(
                        {
                            "detail": (
                                "Internal review has already been completed "
                                "for this Mudra work item."
                            ),
                            "code": (
                                "MUDRA_INTERNAL_REVIEW_ALREADY_COMPLETED"
                            ),
                        },
                        status=409,
                    )

        try:
            qa_prepare_cycle(item, self.principal())
            qa_state = qa_readiness(item)
            if qa_state["enabled"] and not qa_state["ready_for_submission"]:
                return Response(
                    {
                        "detail": "QA preparer checklist is incomplete.",
                        "code": "QA_CHECKLIST_BLOCKED",
                        "qa_readiness": qa_state,
                    },
                    status=400,
                )
            cycle = qa_mark_submitted(
                item,
                self.principal(),
                (request.data or {}).get("comment", ""),
            )
        except ValueError as exc:
            return Response(
                {
                    "detail": str(exc),
                    "code": "QA_CHECKLIST_BLOCKED",
                    "qa_readiness": qa_readiness(item),
                },
                status=400,
            )

        item.submitted_for_review_at = timezone.now()

        if udyam_internal_review_step is not None:
            with transaction.atomic():
                locked_item = (
                    WorkItem.objects
                    .select_for_update()
                    .get(
                        tenant_id=self.principal().tenant_id,
                        id=item.id,
                    )
                )

                locked_item.submitted_for_review_at = (
                    item.submitted_for_review_at
                )

                self._transition(
                    locked_item,
                    WorkStatus.READY_FOR_REVIEW,
                    "Submitted for review.",
                    update_fields={"submitted_for_review_at"},
                )

                self._persist_automated_process_step(
                    locked_item,
                    udyam_internal_review_step,
                    self.principal(),
                    "Submitted for internal review.",
                )

                item = locked_item
        else:
            self._transition(
                item,
                WorkStatus.READY_FOR_REVIEW,
                "Submitted for review.",
                update_fields={"submitted_for_review_at"},
            )

        data = self.get_serializer(item).data
        data["qa_review"] = qa_cycle_summary(cycle)
        return Response(data)

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        item = self.get_object()
        self._require_reviewer(item)
        if item.status != WorkStatus.READY_FOR_REVIEW:
            return Response(
                {"detail": "Only work that is ready for review can be approved."},
                status=400,
            )

        readiness = calculate_document_readiness(item)
        if not readiness["ready_for_review"]:
            return Response(
                {
                    "detail": _MANDATORY_DOCS_MSG,
                    "code": "DOCUMENT_DEPENDENCIES_BLOCKED",
                    "document_readiness": readiness,
                },
                status=400,
            )

        qa_state = qa_readiness(item)
        if qa_state["enabled"] and not qa_state["ready_for_approval"]:
            return Response(
                {
                    "detail": "QA reviewer checklist or issues are incomplete.",
                    "code": "QA_REVIEW_BLOCKED",
                    "qa_readiness": qa_state,
                },
                status=400,
            )

        udyam_internal_review_step = None
        udyam_submit_application_step = None
        mudra_application_step = None
        mudra_credit_eligibility_step = None

        if self._is_udyam_registration(item):
            udyam_internal_review_step = self._udyam_process_step(
                item,
                "INTERNAL_REVIEW",
            )
            udyam_submit_application_step = self._udyam_process_step(
                item,
                "SUBMIT_APPLICATION",
            )

            if (
                udyam_internal_review_step is None
                or udyam_submit_application_step is None
            ):
                return Response(
                    {
                        "detail": (
                            "Required Udyam review/application process "
                            "configuration is unavailable."
                        ),
                        "code": "UDYAM_PROCESS_CONFIGURATION_MISSING",
                    },
                    status=409,
                )

            process_state = (
                WorkProcessState.objects
                .filter(
                    tenant_id=self.principal().tenant_id,
                    work_item_id=item.id,
                )
                .first()
            )

            if (
                process_state is None
                or process_state.current_step_id
                != udyam_internal_review_step.id
            ):
                return Response(
                    {
                        "detail": (
                            "Udyam may be approved only while its durable "
                            "process position is Internal Review & Approval."
                        ),
                        "code": "UDYAM_INTERNAL_REVIEW_STATE_REQUIRED",
                    },
                    status=409,
                )

        elif self._is_mudra_loan(item):
            # Mudra correction: internal review approval is the ONLY path that
            # may advance Mudra from APPLICATION to CREDIT_ELIGIBILITY. This
            # mirrors the Udyam internal-review continuation pattern above
            # (NOT its business states/step names) - a service-specific,
            # isolated branch that does not touch Udyam or any other service.
            mudra_application_step = self._mudra_process_step(
                item,
                "APPLICATION",
            )
            mudra_credit_eligibility_step = self._mudra_process_step(
                item,
                "CREDIT_ELIGIBILITY",
            )

            if (
                mudra_application_step is None
                or mudra_credit_eligibility_step is None
            ):
                return Response(
                    {
                        "detail": (
                            "Required Mudra Application/Credit & Eligibility "
                            "process configuration is unavailable."
                        ),
                        "code": "MUDRA_PROCESS_CONFIGURATION_MISSING",
                    },
                    status=409,
                )

            process_state = (
                WorkProcessState.objects
                .filter(
                    tenant_id=self.principal().tenant_id,
                    work_item_id=item.id,
                )
                .first()
            )

            if (
                process_state is None
                or process_state.current_step_id
                != mudra_application_step.id
            ):
                return Response(
                    {
                        "detail": (
                            "Mudra may be approved only while its durable "
                            "process position is Application & KYC."
                        ),
                        "code": "MUDRA_APPLICATION_STATE_REQUIRED",
                    },
                    status=409,
                )

        comment = (request.data or {}).get("comment", "")
        try:
            cycle = qa_mark_approved(item, self.principal(), comment)
        except ValueError as exc:
            return Response(
                {
                    "detail": str(exc),
                    "code": "QA_REVIEW_BLOCKED",
                    "qa_readiness": qa_readiness(item),
                },
                status=400,
            )

        with transaction.atomic():
            if udyam_submit_application_step is not None:
                locked_item = (
                    WorkItem.objects
                    .select_for_update()
                    .get(
                        tenant_id=self.principal().tenant_id,
                        id=item.id,
                    )
                )

                locked_state = (
                    WorkProcessState.objects
                    .select_for_update()
                    .filter(
                        tenant_id=self.principal().tenant_id,
                        work_item_id=locked_item.id,
                    )
                    .first()
                )

                if (
                    locked_state is None
                    or locked_state.current_step_id
                    != udyam_internal_review_step.id
                ):
                    raise ValidationError(
                        {
                            "detail": (
                                "Udyam process state changed while approval "
                                "was being performed."
                            ),
                            "code": "UDYAM_PROCESS_STATE_CHANGED",
                        }
                    )

                locked_item.completed_at = None

                if comment:
                    locked_item.review_comment = comment

                self._transition(
                    locked_item,
                    WorkStatus.IN_PROGRESS,
                    comment or "Internal review approved.",
                    update_fields={"completed_at", "review_comment"},
                )

                self._persist_automated_process_step(
                    locked_item,
                    udyam_submit_application_step,
                    self.principal(),
                    (
                        "Internal review approved; application reviewed. "
                        "Submitter must now submit the application in the "
                        "government portal."
                    ),
                )

                item = locked_item
            elif mudra_credit_eligibility_step is not None:
                locked_item = (
                    WorkItem.objects
                    .select_for_update()
                    .get(
                        tenant_id=self.principal().tenant_id,
                        id=item.id,
                    )
                )

                locked_state = (
                    WorkProcessState.objects
                    .select_for_update()
                    .filter(
                        tenant_id=self.principal().tenant_id,
                        work_item_id=locked_item.id,
                    )
                    .first()
                )

                if (
                    locked_state is None
                    or locked_state.current_step_id
                    != mudra_application_step.id
                ):
                    raise ValidationError(
                        {
                            "detail": (
                                "Mudra process state changed while approval "
                                "was being performed."
                            ),
                            "code": "MUDRA_PROCESS_STATE_CHANGED",
                        }
                    )

                locked_item.completed_at = None

                if comment:
                    locked_item.review_comment = comment

                self._transition(
                    locked_item,
                    WorkStatus.IN_PROGRESS,
                    comment or "Internal review approved.",
                    update_fields={"completed_at", "review_comment"},
                )

                self._persist_automated_process_step(
                    locked_item,
                    mudra_credit_eligibility_step,
                    self.principal(),
                    (
                        "Internal review approved; Mudra case may proceed "
                        "to Credit & Eligibility."
                    ),
                )

                item = locked_item
            else:
                item.completed_at = timezone.now()

                if comment:
                    item.review_comment = comment

                self._transition(
                    item,
                    WorkStatus.COMPLETED,
                    comment or "Approved and completed.",
                    update_fields={"completed_at", "review_comment"},
                )

        data = self.get_serializer(item).data
        data["qa_review"] = qa_cycle_summary(cycle)
        return Response(data)

    @action(detail=True, methods=["post"])
    def return_for_rework(self, request, pk=None):
        item = self.get_object()
        self._require_reviewer(item)
        if item.status != WorkStatus.READY_FOR_REVIEW:
            return Response(
                {"detail": "Only work that is ready for review can be returned."},
                status=400,
            )
        comment = (request.data or {}).get("comment", "")
        if not comment:
            return Response(
                {"detail": "A review comment is required to return work for rework."},
                status=400,
            )

        udyam_rework_step = None

        if self._is_udyam_registration(item):
            internal_review_step = self._udyam_process_step(
                item,
                "INTERNAL_REVIEW",
            )

            process_state = (
                WorkProcessState.objects
                .filter(
                    tenant_id=self.principal().tenant_id,
                    work_item_id=item.id,
                )
                .first()
            )

            if (
                internal_review_step is not None
                and process_state is not None
                and process_state.current_step_id
                == internal_review_step.id
            ):
                udyam_rework_step = self._udyam_process_step(
                    item,
                    "VERIFICATION_PREPARATION",
                )

                if udyam_rework_step is None:
                    return Response(
                        {
                            "detail": (
                                "Udyam Verification & Preparation process "
                                "configuration is unavailable."
                            ),
                            "code": "UDYAM_PROCESS_CONFIGURATION_MISSING",
                        },
                        status=409,
                    )

        cycle = qa_mark_changes_requested(item, self.principal(), comment)
        with transaction.atomic():
            item.review_comment = comment
            item.completed_at = None
            self._transition(
                item,
                WorkStatus.REWORK_REQUIRED,
                f"Returned for rework: {comment}",
                update_fields={"review_comment", "completed_at"},
            )

            if udyam_rework_step is not None:
                self._persist_automated_process_step(
                    item,
                    udyam_rework_step,
                    self.principal(),
                    (
                        "Returned from internal review for rework: "
                        f"{comment}"
                    ),
                )

        data = self.get_serializer(item).data
        data["qa_review"] = qa_cycle_summary(cycle)
        return Response(data)

    @action(detail=True, methods=["post"])
    def assign(self, request, pk=None):
        """Assign or reassign owner and/or reviewer via a dedicated action.

        Generic writes to owner_user_id/reviewer_user_id are denied by
        ``_deny_control_field_writes``; this is the audited path to change them.
        Only the assigned owner (or an item with no owner yet) may (re)assign,
        matching the owner-control model for non-terminal states. Assignment is
        not permitted on terminal items.
        """
        item = self.get_object()
        if item.status in (WorkStatus.COMPLETED, WorkStatus.CANCELLED):
            return Response(
                {"detail": "Assignment is not permitted on completed or cancelled work."},
                status=400,
            )
        # Owner control: if an owner exists, only that owner may reassign.
        if item.owner_user_id and not ownership.is_owner(item, self.principal()):
            raise PermissionDenied("Only the assigned owner may reassign this work item.")

        data = request.data or {}
        new_owner = data.get("owner_user_id", None)
        new_reviewer = data.get("reviewer_user_id", None)
        if new_owner is None and new_reviewer is None:
            return Response(
                {"detail": "Provide owner_user_id and/or reviewer_user_id."}, status=400
            )

        previous = {"owner_user_id": str(item.owner_user_id or ""), "reviewer_user_id": str(item.reviewer_user_id or "")}
        update_fields = {"updated_by"}
        principal = self.principal()
        with transaction.atomic():
            if new_owner is not None:
                item.owner_user_id = new_owner or None
                update_fields.add("owner_user_id")
            if new_reviewer is not None:
                item.reviewer_user_id = new_reviewer or None
                update_fields.add("reviewer_user_id")
            item.updated_by = principal.principal_id
            item.save(update_fields=list({*update_fields, "row_version"}))
            self._record(
                item,
                "Assignment updated.",
            )
            try:
                if "owner_user_id" in update_fields:
                    record_event(
                        tenant_id=item.tenant_id,
                        principal_id=principal.principal_id,
                        action=AuditAction.OWNER_ASSIGNED,
                        entity_type="WorkItem",
                        entity_id=item.id,
                        summary="Owner assigned",
                        previous={"owner_user_id": previous["owner_user_id"]},
                        new={"owner_user_id": str(item.owner_user_id or "")},
                        request=self.request,
                    )
                if "reviewer_user_id" in update_fields:
                    record_event(
                        tenant_id=item.tenant_id,
                        principal_id=principal.principal_id,
                        action=AuditAction.REVIEWER_ASSIGNED,
                        entity_type="WorkItem",
                        entity_id=item.id,
                        summary="Reviewer assigned",
                        previous={"reviewer_user_id": previous["reviewer_user_id"]},
                        new={"reviewer_user_id": str(item.reviewer_user_id or "")},
                        request=self.request,
                    )
            except Exception as exc:  # noqa: BLE001
                raise MandatoryAuditPersistenceError() from exc
        if (
            "owner_user_id" in update_fields
            and previous["owner_user_id"]
            != str(item.owner_user_id or "")
        ):
            notify_work_assigned(
                item=item,
                actor_principal_id=principal.principal_id,
            )

        return Response(self.get_serializer(item).data)

    @action(detail=True, methods=["post"])
    def reopen(self, request, pk=None):
        """Controlled reopening of completed work (COMPLETED -> REWORK_REQUIRED).

        Reuses the existing status vocabulary rather than introducing a new
        terminal-exit enum: a reopened item re-enters the owner-controlled rework
        path exactly as a review rejection would. Reviewer-gated and requires a
        reason; audited fail-closed via ``_transition``.
        """
        item = self.get_object()
        if item.status != WorkStatus.COMPLETED:
            return Response(
                {"detail": "Only completed work can be reopened."}, status=400
            )
        self._require_reviewer(item)
        comment = request.data.get("comment", "")
        if not comment:
            return Response(
                {"detail": "A reason is required to reopen completed work."}, status=400
            )
        with transaction.atomic():
            item.completed_at = None
            item.review_comment = comment
            self._transition(
                item,
                WorkStatus.REWORK_REQUIRED,
                f"Reopened: {comment}",
                update_fields={"completed_at", "review_comment"},
            )
        return Response(self.get_serializer(item).data)

    @action(detail=True, methods=["get"])
    def attachments(self, request, pk=None):
        item = self.get_object()
        attachments = DocumentAttachment.objects.filter(tenant_id=item.tenant_id, work_item_id=item.id, document_request_id__isnull=True)
        return Response(DocumentAttachmentSerializer(attachments, many=True, context={"request": request}).data)

    @action(detail=True, methods=["post"], parser_classes=[MultiPartParser, FormParser])
    def upload_internal(self, request, pk=None):
        item = self.get_object()
        if not ownership.can_upload_internal(item, self.principal()):
            raise PermissionDenied("Internal document upload is not permitted at this stage.")
        uploads = request.FILES.getlist("files") or ([request.FILES.get("file")] if request.FILES.get("file") else [])
        if not uploads:
            return Response({"detail": "No files were provided."}, status=400)
        principal = self.principal()
        created = []
        try:
            with transaction.atomic():
                for upload in uploads:
                    created.append(_create_attachment(principal=principal, upload=upload, work_item_id=item.id, source="INTERNAL_TEAM"))
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=400)
        self._record(item, f"Uploaded {len(created)} internal document(s).")
        return Response(DocumentAttachmentSerializer(created, many=True, context={"request": request}).data, status=http_status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"])
    def history(self, request, pk=None):
        """Chronological operational story for one Work Item.

        Phase 5.3 deliberately introduces no Timeline table or event engine.
        This endpoint projects already-durable domain history into one ordered
        read model while keeping the existing WorkItem ``history`` action.
        """
        item = self.get_object()
        tenant_id = self.principal().tenant_id

        notes = list(
            WorkNote.objects.filter(
                tenant_id=tenant_id,
                work_item_id=item.id,
            )
        )

        assignments = list(
            AssignmentEvent.objects.filter(
                tenant_id=tenant_id,
                work_item_id=item.id,
            )
        )

        document_requests = list(
            DocumentRequest.objects.filter(
                tenant_id=tenant_id,
                work_item_id=item.id,
            )
        )

        attachments = list(
            DocumentAttachment.objects.filter(
                tenant_id=tenant_id,
                work_item_id=item.id,
            )
        )

        # Some legacy/versioned attachments are linked through the request
        # rather than carrying work_item_id directly.
        request_ids = {
            document_request.id
            for document_request in document_requests
        }

        if request_ids:
            linked_attachments = list(
                DocumentAttachment.objects.filter(
                    tenant_id=tenant_id,
                    document_request_id__in=request_ids,
                )
            )

            seen_attachment_ids = {
                attachment.id
                for attachment in attachments
            }

            attachments.extend(
                attachment
                for attachment in linked_attachments
                if attachment.id not in seen_attachment_ids
            )

        actor_ids = {
            value
            for value in [
                item.created_by,
                *[
                    note.author_user_id
                    for note in notes
                    if note.author_user_id
                ],
                *[
                    assignment.actor_user_id
                    for assignment in assignments
                    if assignment.actor_user_id
                ],
                *[
                    attachment.uploaded_by
                    for attachment in attachments
                    if attachment.uploaded_by
                ],
                *[
                    attachment.reviewed_by
                    for attachment in attachments
                    if attachment.reviewed_by
                ],
            ]
            if value
        }

        employees = Employee.objects.filter(
            tenant_id=tenant_id,
        ).filter(
            models.Q(id__in=actor_ids)
            | models.Q(principal_id__in=actor_ids)
        )

        actor_names = {}

        for employee in employees:
            actor_names[str(employee.id)] = employee.name

            if employee.principal_id:
                actor_names[str(employee.principal_id)] = employee.name

        def actor_name(actor_id):
            if not actor_id:
                return ""

            return actor_names.get(
                str(actor_id),
                "",
            )

        def iso(value):
            return value.isoformat() if value else ""

        events = []

        # --------------------------------------------------------
        # Work creation
        # --------------------------------------------------------

        events.append(
            {
                "id": f"work-created-{item.id}",
                "event_type": "WORK_CREATED",
                "title": "Work created",
                "entry": item.title,
                "detail": "",
                "created_at": iso(item.created_at),
                "actor_id": str(item.created_by or ""),
                "actor_name": actor_name(item.created_by),
                "from_status": "",
                "to_status": WorkStatus.NOT_STARTED,
            }
        )

        # --------------------------------------------------------
        # Existing append-only WorkNote ledger
        #
        # This remains authoritative for workflow transitions and
        # manual/direct assignment changes recorded by WorkItemViewSet.
        # --------------------------------------------------------

        for note in notes:
            # Udyam business-action notes (created by the dedicated Udyam
            # actions via _record) are represented in this read model by the
            # typed process-step AuditEvent projection below, with semantic
            # titles and stage movement.  Suppress the free-text duplicate here
            # so each Udyam business event appears exactly once.  The durable
            # WorkNote row is preserved in the database; only this projection
            # skips it.
            if (note.entry or "").startswith("Udyam ") and not note.to_status:
                continue

            if note.to_status == WorkStatus.IN_PROGRESS:
                if note.from_status == WorkStatus.REWORK_REQUIRED:
                    event_type = "WORK_RESUMED"
                    title = "Work resumed"
                else:
                    event_type = "WORK_STARTED"
                    title = "Work started"

            elif note.to_status == WorkStatus.WAITING_FOR_CLIENT:
                event_type = "WAITING_FOR_CLIENT"
                title = "Waiting for client"

            elif note.to_status == WorkStatus.READY_FOR_REVIEW:
                event_type = "SUBMITTED_FOR_REVIEW"
                title = "Submitted for review"

            elif note.to_status == WorkStatus.REWORK_REQUIRED:
                event_type = "REWORK_REQUIRED"
                title = "Returned for rework"

            elif note.to_status == WorkStatus.COMPLETED:
                event_type = "REVIEW_APPROVED"
                title = "Review approved and completed"

            elif note.to_status == WorkStatus.CANCELLED:
                event_type = "WORK_CANCELLED"
                title = "Work cancelled"

            elif note.entry == "Assignment updated.":
                event_type = "ASSIGNMENT_UPDATED"
                title = "Assignment updated"

            elif note.from_status or note.to_status:
                event_type = "STATUS_CHANGED"
                title = "Work status changed"

            else:
                event_type = "WORK_NOTE"
                title = "Work note"

            events.append(
                {
                    "id": f"note-{note.id}",
                    "event_type": event_type,
                    "title": title,
                    "entry": note.entry,
                    "detail": "",
                    "created_at": iso(note.created_at),
                    "actor_id": str(note.author_user_id or ""),
                    "actor_name": actor_name(
                        note.author_user_id,
                    ),
                    "from_status": note.from_status,
                    "to_status": note.to_status,
                }
            )

        # --------------------------------------------------------
        # Udyam business events from the typed process-step
        # AuditEvent ledger, correlated with the durable Udyam
        # WorkNote written by the SAME action.
        #
        # The AuditEvent supplies the authoritative typed transition
        # (previous/new process step, actor, timestamp).  The matched
        # WorkNote supplies the EVENT-TIME business details (reference,
        # query type/remarks, resolution remarks, certificate) exactly
        # as they were at the moment of the action.
        #
        # We deliberately do NOT read item.operational_data here: that
        # holds CURRENT state and would make an older event (e.g. Query 1)
        # display the values of a newer event (e.g. Query 2).
        # --------------------------------------------------------

        process_state = (
            WorkProcessState.objects
            .filter(
                tenant_id=tenant_id,
                work_item_id=item.id,
            )
            .first()
        )

        if process_state is not None:
            process_events = list(
                AuditEvent.objects.filter(
                    tenant_id=tenant_id,
                    entity_type="WorkProcessState",
                    entity_id=process_state.id,
                    action=AuditAction.STATUS_CHANGE,
                ).order_by("created_at", "id")
            )

            # Durable Udyam business-action notes, kept in time order.  Each
            # note is consumed at most once so two events never share detail.
            udyam_notes = sorted(
                (
                    n for n in notes
                    if (n.entry or "").startswith("Udyam ") and not n.to_status
                ),
                key=lambda n: (n.created_at, str(n.id)),
            )
            consumed_note_ids = set()

            # Stable prefix per transition type.  These strings are written by
            # the dedicated Udyam actions and are the reliable correlation key
            # (combined with nearest timestamp).
            _SUBMIT_PREFIX = "Udyam application submitted."
            _QUERY_PREFIX = "Udyam query / issue reported."
            _RESOLVE_PREFIX = "Udyam query / issue resolved."
            _COMPLETE_PREFIX = "Udyam registration completed"

            def _match_note(prefix, when):
                """Nearest not-yet-consumed Udyam note with this prefix.

                Correlation dimensions: same work item + tenant (the notes
                queryset is already scoped to both), matching business-action
                prefix, and closest timestamp to the typed event.  Returns the
                note or None; never guesses across a different prefix.
                """
                best = None
                best_delta = None
                for candidate in udyam_notes:
                    if candidate.id in consumed_note_ids:
                        continue
                    if not (candidate.entry or "").startswith(prefix):
                        continue
                    delta = abs(
                        (candidate.created_at - when).total_seconds()
                    )
                    if best is None or delta < best_delta:
                        best = candidate
                        best_delta = delta
                return best

            for process_event in process_events:
                prev_code = (process_event.previous_values or {}).get(
                    "process_step_code", ""
                )
                new_code = (process_event.new_values or {}).get(
                    "process_step_code", ""
                )
                when = process_event.created_at

                if prev_code == "QUERY_RESOLUTION" and new_code == "APPLICATION_SUBMISSION":
                    event_type = "UDYAM_QUERY_RESOLVED"
                    title = "Query resolved"
                    matched = _match_note(_RESOLVE_PREFIX, when)
                elif new_code == "QUERY_RESOLUTION":
                    event_type = "UDYAM_QUERY_RECEIVED"
                    title = "Query / issue received"
                    matched = _match_note(_QUERY_PREFIX, when)
                elif new_code == "COMPLETION":
                    event_type = "UDYAM_REGISTRATION_COMPLETED"
                    title = "Registration completed"
                    matched = _match_note(_COMPLETE_PREFIX, when)
                elif new_code == "APPLICATION_SUBMISSION":
                    # Arrival at APPLICATION_SUBMISSION from SUBMIT_APPLICATION
                    # (or any non-query origin) is the submission event.
                    event_type = "UDYAM_APPLICATION_SUBMITTED"
                    title = "Application submitted"
                    matched = _match_note(_SUBMIT_PREFIX, when)
                else:
                    event_type = "UDYAM_PROCESS_STEP"
                    title = process_event.summary or "Process step changed"
                    matched = None

                # Event-time detail comes from the matched WorkNote, never from
                # current operational_data.  Fallback: the typed event summary.
                if matched is not None:
                    consumed_note_ids.add(matched.id)
                    detail = matched.entry
                    detail_actor_id = matched.author_user_id
                else:
                    detail = process_event.summary
                    detail_actor_id = process_event.actor_principal_id

                events.append(
                    {
                        "id": f"process-{process_event.id}",
                        "event_type": event_type,
                        "title": title,
                        "entry": detail,
                        "detail": detail,
                        "created_at": iso(process_event.created_at),
                        "actor_id": str(
                            process_event.actor_principal_id
                            or detail_actor_id
                            or ""
                        ),
                        "actor_name": actor_name(
                            process_event.actor_principal_id
                            or detail_actor_id
                        ),
                        "from_status": prev_code,
                        "to_status": new_code,
                    }
                )

        # --------------------------------------------------------
        # Existing append-only AssignmentEvent ledger
        # --------------------------------------------------------

        for assignment in assignments:
            owner = Employee.objects.filter(
                tenant_id=tenant_id,
                id=assignment.owner_user_id,
            ).first() if assignment.owner_user_id else None

            reviewer = Employee.objects.filter(
                tenant_id=tenant_id,
                id=assignment.reviewer_user_id,
            ).first() if assignment.reviewer_user_id else None

            event_type = str(assignment.event_type)

            title_map = {
                "RECOMMENDED_APPLIED": "Work assigned",
                "OVERRIDE_APPLIED": "Assignment override applied",
                "REASSIGNED": "Work reassigned",
                "REVIEWER_SET": "Reviewer assigned",
            }

            detail_parts = []

            if owner:
                detail_parts.append(
                    f"Owner: {owner.name}"
                )

            if reviewer:
                detail_parts.append(
                    f"Reviewer: {reviewer.name}"
                )

            if assignment.reason:
                detail_parts.append(
                    assignment.reason
                )

            events.append(
                {
                    "id": f"assignment-{assignment.id}",
                    "event_type": event_type,
                    "title": title_map.get(
                        event_type,
                        "Assignment updated",
                    ),
                    "entry": " Ã‚Â· ".join(detail_parts),
                    "detail": "",
                    "created_at": iso(assignment.created_at),
                    "actor_id": str(
                        assignment.actor_user_id or ""
                    ),
                    "actor_name": actor_name(
                        assignment.actor_user_id,
                    ),
                    "from_status": "",
                    "to_status": "",
                }
            )

        # --------------------------------------------------------
        # Existing DocumentRequest lifecycle
        # --------------------------------------------------------

        request_names = {
            document_request.id: document_request.name
            for document_request in document_requests
        }

        for document_request in document_requests:
            sent_time = (
                document_request.sent_at
                or document_request.created_at
            )

            events.append(
                {
                    "id": f"document-request-{document_request.id}",
                    "event_type": "DOCUMENT_REQUESTED",
                    "title": "Document requested",
                    "entry": document_request.name,
                    "detail": str(
                        document_request.request_channel or ""
                    ),
                    "created_at": iso(sent_time),
                    "actor_id": str(
                        document_request.created_by or ""
                    ),
                    "actor_name": actor_name(
                        document_request.created_by,
                    ),
                    "from_status": "",
                    "to_status": str(
                        document_request.status or ""
                    ),
                }
            )

        # --------------------------------------------------------
        # Existing DocumentAttachment lifecycle
        # --------------------------------------------------------

        for attachment in attachments:
            document_name = request_names.get(
                attachment.document_request_id,
                attachment.original_name,
            )

            source = str(
                attachment.source or ""
            )

            upload_title = (
                "Document received from client"
                if source == "CLIENT"
                else "Document uploaded"
            )

            events.append(
                {
                    "id": f"attachment-upload-{attachment.id}",
                    "event_type": "DOCUMENT_RECEIVED",
                    "title": upload_title,
                    "entry": document_name,
                    "detail": attachment.original_name,
                    "created_at": iso(attachment.created_at),
                    "actor_id": str(
                        attachment.uploaded_by or ""
                    ),
                    "actor_name": actor_name(
                        attachment.uploaded_by,
                    ),
                    "from_status": "",
                    "to_status": str(
                        attachment.review_status or ""
                    ),
                }
            )

            if attachment.reviewed_at:
                review_status = str(
                    attachment.review_status or ""
                )

                if review_status == AttachmentReviewStatus.ACCEPTED:
                    review_title = "Document accepted"
                    review_type = "DOCUMENT_ACCEPTED"

                elif review_status == AttachmentReviewStatus.REJECTED:
                    review_title = "Document rejected"
                    review_type = "DOCUMENT_REJECTED"

                else:
                    review_title = "Document reviewed"
                    review_type = "DOCUMENT_REVIEWED"

                events.append(
                    {
                        "id": f"attachment-review-{attachment.id}",
                        "event_type": review_type,
                        "title": review_title,
                        "entry": document_name,
                        "detail": str(
                            attachment.review_comment or ""
                        ),
                        "created_at": iso(
                            attachment.reviewed_at
                        ),
                        "actor_id": str(
                            attachment.reviewed_by or ""
                        ),
                        "actor_name": actor_name(
                            attachment.reviewed_by,
                        ),
                        "from_status": "PENDING_REVIEW",
                        "to_status": review_status,
                    }
                )

        # Oldest -> newest creates the natural operational story.
        #
        # Multiple domain events can legitimately resolve to the same
        # timestamp. Work creation is the causal anchor of every later
        # event, so it wins only that timestamp tie. The remaining events
        # keep their existing deterministic id ordering.
        events.sort(
            key=lambda event: (
                event["created_at"],
                0
                if event["event_type"] == "WORK_CREATED"
                else 1,
                event["id"],
            )
        )

        return Response(events)


class WorkNoteViewSet(TenantModelViewSet):
    queryset = WorkNote.objects.all()
    serializer_class = WorkNoteSerializer
    search_fields = ["entry"]
    http_method_names = ["get", "head", "options"]

    def get_queryset(self):
        qs = super().get_queryset()
        value = self.request.query_params.get("work_item_id")
        return qs.filter(work_item_id=value) if value else qs


class DocumentRequestViewSet(TenantModelViewSet):
    permission_classes = [
        IsAuthenticated,
        DocumentRequestAccessPermission,
    ]
    queryset = DocumentRequest.objects.all()
    serializer_class = DocumentRequestSerializer
    search_fields = ["name", "notes", "description", "remarks"]
    ordering_fields = ["due_date", "created_at", "status"]

    def _work_item_for(self, doc):
        """Resolve the parent WorkItem for a document request, tenant-scoped."""
        return WorkItem.objects.filter(
            tenant_id=doc.tenant_id, id=doc.work_item_id
        ).first()

    def destroy(self, request, *args, **kwargs):
        # C4: deletion is never permitted; existing DELETE would destroy
        # attachment/review/audit history. Blocked rather than soft-deleted.
        raise PermissionDenied("Deleting document requests is not permitted.")

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        for field in (
            "status",
            "client_id",
            "work_item_id",
            "category",
            "financial_year",
            "assessment_year",
            "filing_period",
        ):
            value = params.get(field)
            if value:
                qs = qs.filter(**{field: value})
        expiry_state = params.get("expiry_state")
        if expiry_state == "EXPIRED":
            qs = qs.filter(expires_on__lt=timezone.now().date())
        elif expiry_state == "EXPIRING_30_DAYS":
            today = timezone.now().date()
            qs = qs.filter(
                expires_on__gte=today,
                expires_on__lte=today + timedelta(days=30),
            )
        elif expiry_state == "NO_EXPIRY":
            qs = qs.filter(expires_on__isnull=True)

        return qs

    def _validate_contact(self, serializer):
        contact_id = serializer.validated_data.get("requested_from_contact_id", getattr(serializer.instance, "requested_from_contact_id", None))
        client_id = serializer.validated_data.get("client_id", getattr(serializer.instance, "client_id", None))
        if not contact_id:
            raise PermissionDenied("Select an active client contact who can receive document requests.")
        if not ClientContact.objects.filter(tenant_id=self.principal().tenant_id, id=contact_id, client_id=client_id, is_active=True, can_receive_document_requests=True).exists():
            raise PermissionDenied("The selected contact cannot receive document requests for this client.")

    def perform_create(self, serializer):
        self._validate_contact(serializer)
        principal = self.principal()
        work_item_id = serializer.validated_data.get("work_item_id")
        # Standalone request (no work_item_id) keeps its existing contract:
        # tenant + contact validation only, no WorkItem ownership/lifecycle gate.
        if work_item_id:
            item = WorkItem.objects.filter(
                tenant_id=principal.tenant_id, id=work_item_id
            ).first()
            # An invalid/non-visible work_item_id is NOT treated as standalone.
            if item is None:
                raise PermissionDenied("The referenced work item was not found.")
            if not ownership.can_mutate_document_request(item, principal):
                raise PermissionDenied(
                    "Document requests can only be managed by the assigned owner "
                    "while the work item is in an editable stage."
                )
        with transaction.atomic():
            instance = serializer.save(
                tenant_id=principal.tenant_id,
                created_by=principal.principal_id,
                updated_by=principal.principal_id,
                sent_at=timezone.now(),
                requested_date=timezone.now().date(),
            )
            # Mandatory audit inside the same transaction: a persistence failure
            # rolls the document-request creation back (no unaudited mutation).
            record_event(
                tenant_id=principal.tenant_id,
                principal_id=principal.principal_id,
                action=AuditAction.DOCUMENT_REQUEST_CREATED,
                entity_type="DocumentRequest",
                entity_id=instance.id,
                summary=getattr(instance, "name", ""),
                new={"name": getattr(instance, "name", ""), "status": getattr(instance, "status", "")},
                request=self.request,
            )

    def perform_update(self, serializer):
        self._validate_contact(serializer)
        principal = self.principal()
        instance = serializer.instance
        # Standalone request keeps its existing contract on update too.
        if instance.work_item_id:
            item = self._work_item_for(instance)
            if item is None:
                raise PermissionDenied("The referenced work item was not found.")
            if not ownership.can_mutate_document_request(item, principal):
                raise PermissionDenied(
                    "Document requests can only be managed by the assigned owner "
                    "while the work item is in an editable stage."
                )
        serializer.save(updated_by=principal.principal_id)

    @action(detail=True, methods=["post"])
    def verify(self, request, pk=None):
        """Compatibility endpoint: waive the request or review its newest pending attachment."""
        doc = self.get_object()
        target = request.data.get("status")
        comment = request.data.get("comment", "")
        principal = self.principal()

        item = self._work_item_for(doc)
        # Preserve the established standalone-document contract: requests with
        # no WorkItem have no assigned reviewer to resolve, so their existing
        # internal verification path remains available.  For linked requests,
        # require the assigned reviewer but do not impose a workflow-state gate;
        # existing completion and evidence flows verify documents before and
        # during review.
        if item is not None and not ownership.is_reviewer(item, principal):
            raise PermissionDenied(
                "Only the assigned reviewer may verify documents for this work item."
            )

        if target not in (
            AttachmentReviewStatus.ACCEPTED,
            AttachmentReviewStatus.REJECTED,
            DocumentRequestStatus.WAIVED,
        ):
            return Response(
                {"detail": "Verification status must be ACCEPTED, REJECTED or WAIVED."},
                status=400,
            )
        if target in (AttachmentReviewStatus.REJECTED, DocumentRequestStatus.WAIVED) and not comment:
            return Response(
                {"detail": "A comment is required for rejection or waiver."},
                status=400,
            )

        with transaction.atomic():
            if target == DocumentRequestStatus.WAIVED:
                doc.status = DocumentRequestStatus.WAIVED
                doc.verification_comment = comment
                doc.verified_at = timezone.now()
                doc.verified_by = principal.principal_id
                doc.updated_by = principal.principal_id
                doc.save(
                    update_fields=[
                        "status",
                        "verification_comment",
                        "verified_at",
                        "verified_by",
                        "updated_by",
                        "row_version",
                    ]
                )
            else:
                attachment = (
                    DocumentAttachment.objects.select_for_update()
                    .filter(
                        tenant_id=doc.tenant_id,
                        document_request_id=doc.id,
                        review_status=AttachmentReviewStatus.PENDING_REVIEW,
                    )
                    .order_by("-created_at", "-id")
                    .first()
                )
                if attachment is None:
                    return Response(
                        {"detail": "No pending attachment is available for review."},
                        status=400,
                    )
                attachment.review_status = target
                attachment.review_comment = comment
                attachment.reviewed_at = timezone.now()
                attachment.reviewed_by = principal.principal_id
                attachment.updated_by = principal.principal_id
                attachment.save(
                    update_fields=[
                        "review_status",
                        "review_comment",
                        "reviewed_at",
                        "reviewed_by",
                        "updated_by",
                        "row_version",
                    ]
                )
                recalculate_document_request_status(
                    doc,
                    updated_by=principal.principal_id,
                )

        doc.refresh_from_db()
        return Response(self.get_serializer(doc).data)

    @action(detail=True, methods=["get"])
    def attachments(self, request, pk=None):
        doc = self.get_object()
        items = DocumentAttachment.objects.filter(
            tenant_id=self.principal().tenant_id, document_request_id=doc.id
        )
        return Response(DocumentAttachmentSerializer(items, many=True, context={"request": request}).data)

    @action(detail=True, methods=["post"], parser_classes=[MultiPartParser, FormParser])
    def upload(self, request, pk=None):
        doc = self.get_object()
        # Requested-document upload stays InternalPrincipal-based (no client auth).
        # Preserve the established evidence-completion flow: a missing mandatory
        # document may still be uploaded while work is READY_FOR_REVIEW so the
        # reviewer can verify it and complete the item.  Only terminal work is
        # closed to further requested-document uploads.
        if doc.work_item_id:
            item = WorkItem.objects.filter(
                tenant_id=self.principal().tenant_id, id=doc.work_item_id
            ).first()
            if item is not None and item.status in ("COMPLETED", "CANCELLED"):
                raise PermissionDenied(
                    "Documents cannot be uploaded after the work item is closed."
                )
        uploads = request.FILES.getlist("files") or ([request.FILES.get("file")] if request.FILES.get("file") else [])
        if not uploads:
            return Response({"detail": "No files were provided."}, status=400)
        principal = self.principal()
        source = request.data.get("source", "CLIENT")
        upload_intent = request.data.get(
            "upload_intent",
            "NEW_VERSION",
        )
        allow_duplicate = (
            str(
                request.data.get(
                    "allow_duplicate",
                    "",
                )
            ).lower()
            in {"1", "true", "yes"}
        )

        created = []

        try:
            with transaction.atomic():
                for upload in uploads:
                    created.append(
                        _create_attachment(
                            principal=principal,
                            upload=upload,
                            document_request_id=doc.id,
                            work_item_id=doc.work_item_id,
                            source=source,
                            upload_intent=upload_intent,
                            allow_duplicate=allow_duplicate,
                        )
                    )
                if not doc.received_date:
                    doc.received_date = timezone.now().date()
                    doc.updated_by = principal.principal_id
                    doc.save(update_fields=["received_date", "updated_by", "row_version"])
                recalculate_document_request_status(
                    doc,
                    updated_by=principal.principal_id,
                )
        except DuplicateAttachmentError as exc:
            return Response(
                {
                    "detail": str(exc),
                    "code": "DUPLICATE_ATTACHMENT",
                    "existing_attachment": (
                        DocumentAttachmentSerializer(
                            exc.attachment,
                            context={"request": request},
                        ).data
                    ),
                    "allowed_actions": [
                        "CANCEL",
                        "KEEP_AS_VERSION",
                    ],
                },
                status=http_status.HTTP_409_CONFLICT,
            )
        except ValueError as exc:
            return Response(
                {"detail": str(exc)},
                status=400,
            )

        return Response(
            DocumentAttachmentSerializer(
                created,
                many=True,
                context={"request": request},
            ).data,
            status=http_status.HTTP_201_CREATED,
        )


class DocumentAttachmentViewSet(TenantModelViewSet):
    permission_classes = [
        IsAuthenticated,
        DocumentAttachmentAccessPermission,
    ]
    queryset = DocumentAttachment.objects.all()
    serializer_class = DocumentAttachmentSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        request_id = self.request.query_params.get("document_request_id")
        work_item_id = self.request.query_params.get("work_item_id")
        if request_id:
            qs = qs.filter(document_request_id=request_id)
        if work_item_id:
            qs = qs.filter(work_item_id=work_item_id)
        return qs

    def _work_item_for(self, attachment):
        """Resolve the parent WorkItem for an attachment, tenant-scoped."""
        return WorkItem.objects.filter(
            tenant_id=attachment.tenant_id, id=attachment.work_item_id
        ).first()

    def create(self, request, *args, **kwargs):
        # C4: attachments are created only via the approved upload actions
        # (WorkItem.upload_internal / DocumentRequest.upload), never generically.
        raise PermissionDenied("Attachments are created only through the upload actions.")

    def update(self, request, *args, **kwargs):
        # C4: no generic attachment mutation; review is a dedicated action.
        raise PermissionDenied("Attachments cannot be edited directly.")

    def partial_update(self, request, *args, **kwargs):
        raise PermissionDenied("Attachments cannot be edited directly.")

    def destroy(self, request, *args, **kwargs):
        # C4: deletion is never permitted; existing DELETE would destroy
        # attachment file, review evidence and audit history.
        raise PermissionDenied("Deleting attachments is not permitted.")

    @action(detail=True, methods=["post"])
    def review(self, request, pk=None):
        attachment = self.get_object()
        target = request.data.get("status")
        comment = request.data.get("comment", "")
        principal = self.principal()
        item = self._work_item_for(attachment)
        # Standalone document-request attachments have no WorkItem reviewer.
        # Preserve their existing internal review path.  Linked attachments are
        # restricted to the assigned reviewer, without adding a state-only gate.
        if item is not None and not ownership.is_reviewer(item, principal):
            raise PermissionDenied(
                "Only the assigned reviewer may review attachments for this work item."
            )

        if target not in (AttachmentReviewStatus.ACCEPTED, AttachmentReviewStatus.REJECTED):
            return Response(
                {"detail": "Attachment review status must be ACCEPTED or REJECTED."},
                status=400,
            )
        if target == AttachmentReviewStatus.REJECTED and not comment:
            return Response(
                {"detail": "A comment is required for rejection."},
                status=400,
            )
        if not attachment.document_request_id:
            return Response(
                {"detail": "Only document-request attachments can be reviewed."},
                status=400,
            )
        if attachment.review_status != AttachmentReviewStatus.PENDING_REVIEW:
            return Response(
                {"detail": "Only pending attachments can be reviewed."},
                status=400,
            )

        with transaction.atomic():
            attachment.review_status = target
            attachment.review_comment = comment
            attachment.reviewed_at = timezone.now()
            attachment.reviewed_by = principal.principal_id
            attachment.updated_by = principal.principal_id
            attachment.save(
                update_fields=[
                    "review_status",
                    "review_comment",
                    "reviewed_at",
                    "reviewed_by",
                    "updated_by",
                    "row_version",
                ]
            )
            doc = DocumentRequest.objects.select_for_update().get(
                tenant_id=attachment.tenant_id,
                id=attachment.document_request_id,
            )
            recalculate_document_request_status(
                doc,
                updated_by=principal.principal_id,
            )
            # Mandatory audit inside the same transaction as the review.
            record_event(
                tenant_id=attachment.tenant_id,
                principal_id=principal.principal_id,
                action=(
                    AuditAction.ATTACHMENT_ACCEPTED
                    if target == AttachmentReviewStatus.ACCEPTED
                    else AuditAction.ATTACHMENT_REJECTED
                ),
                entity_type="DocumentAttachment",
                entity_id=attachment.id,
                summary=f"Attachment {target}",
                new={"review_status": target},
                request=self.request,
            )

        attachment.refresh_from_db()
        return Response(self.get_serializer(attachment).data)

    @action(
        detail=True,
        methods=["post"],
        url_path="resolve-duplicate",
    )
    def resolve_duplicate(self, request, pk=None):
        attachment = self.get_object()
        resolution = request.data.get("resolution")
        principal = self.principal()
        item = self._work_item_for(attachment)

        if item is not None and not ownership.is_reviewer(
            item,
            principal,
        ):
            raise PermissionDenied(
                "Only the assigned reviewer may resolve duplicate "
                "attachments for this work item."
            )

        if not attachment.is_duplicate:
            return Response(
                {
                    "detail": (
                        "This attachment is not marked as a "
                        "duplicate."
                    )
                },
                status=400,
            )

        if resolution not in {
            DuplicateResolutionStatus.CONFIRMED_DUPLICATE,
            DuplicateResolutionStatus.KEPT_AS_VERSION,
        }:
            return Response(
                {
                    "detail": (
                        "Resolution must be CONFIRMED_DUPLICATE "
                        "or KEPT_AS_VERSION."
                    )
                },
                status=400,
            )

        with transaction.atomic():
            attachment.duplicate_resolution = resolution
            attachment.updated_by = principal.principal_id

            update_fields = {
                "duplicate_resolution",
                "updated_by",
                "row_version",
            }

            if (
                resolution
                == DuplicateResolutionStatus.CONFIRMED_DUPLICATE
            ):
                attachment.review_status = (
                    AttachmentReviewStatus.SUPERSEDED
                )
                attachment.is_canonical = False
                update_fields.update(
                    {
                        "review_status",
                        "is_canonical",
                    }
                )

            attachment.save(
                update_fields=list(update_fields)
            )

            if attachment.document_request_id:
                doc = (
                    DocumentRequest.objects
                    .select_for_update()
                    .get(
                        tenant_id=attachment.tenant_id,
                        id=attachment.document_request_id,
                    )
                )

                recalculate_document_request_status(
                    doc,
                    updated_by=principal.principal_id,
                )

            record_event(
                tenant_id=attachment.tenant_id,
                principal_id=principal.principal_id,
                action=AuditAction.STATUS_CHANGE,
                entity_type="DocumentAttachment",
                entity_id=attachment.id,
                summary=(
                    "Duplicate attachment resolved as "
                    f"{resolution}"
                ),
                new={
                    "duplicate_resolution": resolution,
                    "review_status": attachment.review_status,
                },
                request=self.request,
            )

        attachment.refresh_from_db()

        return Response(
            self.get_serializer(attachment).data
        )

    @action(
        detail=True,
        methods=["post"],
        url_path="mark-canonical",
    )
    def mark_canonical(self, request, pk=None):
        attachment = self.get_object()
        principal = self.principal()
        item = self._work_item_for(attachment)

        if item is not None and not ownership.is_reviewer(
            item,
            principal,
        ):
            raise PermissionDenied(
                "Only the assigned reviewer may select the "
                "canonical attachment for this work item."
            )

        if not attachment.document_request_id:
            return Response(
                {
                    "detail": (
                        "Canonical selection is supported only for "
                        "document-request attachments."
                    )
                },
                status=400,
            )

        if (
            attachment.review_status
            != AttachmentReviewStatus.ACCEPTED
        ):
            return Response(
                {
                    "detail": (
                        "Only an accepted attachment can be marked "
                        "as canonical."
                    )
                },
                status=400,
            )

        if (
            attachment.is_duplicate
            and attachment.duplicate_resolution
            != DuplicateResolutionStatus.KEPT_AS_VERSION
        ):
            return Response(
                {
                    "detail": (
                        "Resolve the duplicate before selecting it "
                        "as canonical."
                    )
                },
                status=400,
            )

        with transaction.atomic():
            (
                DocumentAttachment.objects
                .select_for_update()
                .filter(
                    tenant_id=attachment.tenant_id,
                    document_request_id=(
                        attachment.document_request_id
                    ),
                    is_canonical=True,
                )
                .exclude(id=attachment.id)
                .update(
                    is_canonical=False,
                    updated_by=principal.principal_id,
                )
            )

            attachment.is_canonical = True
            attachment.updated_by = principal.principal_id
            attachment.save(
                update_fields=[
                    "is_canonical",
                    "updated_by",
                    "row_version",
                ]
            )

            record_event(
                tenant_id=attachment.tenant_id,
                principal_id=principal.principal_id,
                action=AuditAction.STATUS_CHANGE,
                entity_type="DocumentAttachment",
                entity_id=attachment.id,
                summary="Canonical attachment selected",
                new={"is_canonical": True},
                request=self.request,
            )

        attachment.refresh_from_db()

        return Response(
            self.get_serializer(attachment).data
        )

    @action(detail=True, methods=["get"])
    def download(self, request, pk=None):
        attachment = self.get_object()  # tenant-scoped by base queryset
        # Confirm the parent document request exists in the same tenant.
        parent_ok = False
        if attachment.document_request_id:
            parent_ok = DocumentRequest.objects.filter(tenant_id=self.principal().tenant_id, id=attachment.document_request_id).exists()
        elif attachment.work_item_id:
            parent_ok = WorkItem.objects.filter(tenant_id=self.principal().tenant_id, id=attachment.work_item_id).exists()
        if not parent_ok:
            raise Http404("File is not available.")
        try:
            handle = attachment.file.open("rb")
        except (FileNotFoundError, ValueError) as exc:
            raise Http404("File is no longer available.") from exc
        return FileResponse(handle, as_attachment=True, filename=attachment.original_name)
