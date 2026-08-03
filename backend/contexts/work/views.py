from __future__ import annotations

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
)
from contexts.identity.models import Employee

from . import ownership
from .document_intelligence import calculate_document_readiness
from contexts.audit.recording import record_event
from contexts.audit.models import AuditAction

from .models import (
    AttachmentReviewStatus,
    DocumentAttachment,
    DuplicateResolutionStatus,
    DocumentRequest,
    DocumentRequestStatus,
    WorkItem,
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

        if contact is None:
            if strict:
                raise ValidationError(
                    {
                        "detail": (
                            "No active client contact is eligible to "
                            "receive document requests."
                        )
                    }
                )

            return {
                "created": 0,
                "existing": 0,
                "skipped": "NO_ELIGIBLE_CLIENT_CONTACT",
                "requests": [],
            }

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
                    "requested_from_contact_id": contact.id,
                    "request_channel": request_channel,
                    "sent_at": timezone.now(),
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
        qs = super().get_queryset()
        params = self.request.query_params
        for field in ("status", "priority", "client_id", "service_id", "owner_user_id", "reviewer_user_id"):
            value = params.get(field)
            if value:
                qs = qs.filter(**{field: value})
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

    def update(self, request, *args, **kwargs):
        item = self.get_object()
        if not ownership.can_edit_work_item(item, self.principal()):
            raise PermissionDenied(
                "This work item is read-only for you at its current stage."
            )
        self._deny_control_field_writes(item)
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
        if not item.reviewer_user_id:
            raise PermissionDenied("Only the assigned reviewer may perform this action.")
        linked = Employee.objects.filter(
            tenant_id=principal.tenant_id,
            id=item.reviewer_user_id,
            principal_id=principal.principal_id,
            is_active=True,
        ).exists()
        if not linked:
            raise PermissionDenied("Only the assigned reviewer may perform this action.")

    @transaction.atomic
    def _transition(self, item, target, entry, *, update_fields):
        previous = item.status
        item.status = target
        fields = {"status", "updated_by", *update_fields}
        item.updated_by = self.principal().principal_id
        item.save(update_fields=list(fields))
        self._record(item, entry or f"Status changed to {target}.", previous, target)
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
            # Raise a DRF APIException from inside the atomic boundary. Django
            # rolls back the business mutation before DRF renders the controlled
            # 503 response, so mandatory audit persistence remains fail-closed.
            raise MandatoryAuditPersistenceError() from exc
        return previous

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

        item.submitted_for_review_at = timezone.now()

        self._transition(
            item,
            WorkStatus.READY_FOR_REVIEW,
            "Submitted for review.",
            update_fields={"submitted_for_review_at"},
        )

        return Response(self.get_serializer(item).data)

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        item = self.get_object()
        self._require_reviewer(item)
        if item.status != WorkStatus.READY_FOR_REVIEW:
            return Response({"detail": "Only work that is ready for review can be approved."}, status=400)
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
        comment = request.data.get("comment", "")
        with transaction.atomic():
            item.completed_at = timezone.now()
            if comment:
                item.review_comment = comment
            self._transition(
                item, WorkStatus.COMPLETED, comment or "Approved and completed.",
                update_fields={"completed_at", "review_comment"},
            )
        return Response(self.get_serializer(item).data)

    @action(detail=True, methods=["post"])
    def return_for_rework(self, request, pk=None):
        item = self.get_object()
        self._require_reviewer(item)
        if item.status != WorkStatus.READY_FOR_REVIEW:
            return Response({"detail": "Only work that is ready for review can be returned."}, status=400)
        comment = request.data.get("comment", "")
        if not comment:
            return Response({"detail": "A review comment is required to return work for rework."}, status=400)
        with transaction.atomic():
            item.review_comment = comment
            item.completed_at = None
            self._transition(
                item, WorkStatus.REWORK_REQUIRED, f"Returned for rework: {comment}",
                update_fields={"review_comment", "completed_at"},
            )
        return Response(self.get_serializer(item).data)

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
        item = self.get_object()
        notes = WorkNote.objects.filter(tenant_id=self.principal().tenant_id, work_item_id=item.id)
        return Response(WorkNoteSerializer(notes, many=True).data)


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
