from __future__ import annotations

from datetime import date

from rest_framework import serializers

from contexts.clients.models import Client, ClientContact
from contexts.configuration.models import Domain, Service
from contexts.identity.models import Employee

from . import ownership
from .document_intelligence import calculate_document_readiness
from .models import DocumentAttachment, DocumentRequest, WorkItem, WorkNote

_AUDIT = ("id", "tenant_id", "created_at", "created_by", "updated_at", "updated_by", "row_version")


def _name_map(model, tenant_id, field="name"):
    return {row.id: getattr(row, field) for row in model.objects.filter(tenant_id=tenant_id)}


class WorkItemSerializer(serializers.ModelSerializer):
    client_name = serializers.SerializerMethodField()
    service_name = serializers.SerializerMethodField()
    owner_name = serializers.SerializerMethodField()
    reviewer_name = serializers.SerializerMethodField()
    is_overdue = serializers.SerializerMethodField()
    current_controller = serializers.SerializerMethodField()
    current_controller_name = serializers.SerializerMethodField()
    is_locked = serializers.SerializerMethodField()
    can_edit = serializers.SerializerMethodField()
    can_submit_for_review = serializers.SerializerMethodField()
    can_review = serializers.SerializerMethodField()
    can_upload_internal = serializers.SerializerMethodField()

    document_ready = serializers.SerializerMethodField()
    document_readiness_state = serializers.SerializerMethodField()
    document_health_score = serializers.SerializerMethodField()
    mandatory_document_total = serializers.SerializerMethodField()
    mandatory_document_satisfied = serializers.SerializerMethodField()
    mandatory_document_missing = serializers.SerializerMethodField()
    document_blockers = serializers.SerializerMethodField()

    class Meta:
        model = WorkItem
        fields = "__all__"
        read_only_fields = (*_AUDIT, "submitted_for_review_at", "completed_at")

    def _clients(self):
        if not hasattr(self, "_client_cache"):
            self._client_cache = {
                c.id: (c.trade_name or c.legal_name)
                for c in Client.objects.filter(tenant_id=self._tenant())
            }
        return self._client_cache

    def _tenant(self):
        request = self.context.get("request")
        return request.user.tenant_id if request else None

    def get_client_name(self, obj):
        return self._clients().get(obj.client_id, "")

    def get_service_name(self, obj):
        if not obj.service_id:
            return ""
        service = Service.objects.filter(tenant_id=obj.tenant_id, id=obj.service_id).first()
        return service.name if service else ""

    def get_owner_name(self, obj):
        return self._employee_name(obj.owner_user_id, obj.tenant_id)

    def get_reviewer_name(self, obj):
        return self._employee_name(obj.reviewer_user_id, obj.tenant_id)

    @staticmethod
    def _employee_name(user_id, tenant_id):
        if not user_id:
            return ""
        emp = Employee.objects.filter(tenant_id=tenant_id, id=user_id).first()
        return emp.name if emp else ""

    @staticmethod
    def get_is_overdue(obj):
        from datetime import date

        if not obj.due_date or obj.status in ("COMPLETED", "CANCELLED"):
            return False
        return obj.due_date < date.today()

    # -- C4 controller/permission fields (read-only, derived) ----------
    def _principal(self):
        request = self.context.get("request")
        return getattr(request, "user", None) if request else None

    def get_current_controller(self, obj):
        return ownership.current_controller(obj)

    def get_current_controller_name(self, obj):
        controller = ownership.current_controller(obj)
        if controller == ownership.CONTROLLER_OWNER:
            return self._employee_name(obj.owner_user_id, obj.tenant_id)
        if controller == ownership.CONTROLLER_REVIEWER:
            return self._employee_name(obj.reviewer_user_id, obj.tenant_id)
        return ""

    def get_is_locked(self, obj):
        # Locked for the current principal when they cannot edit and are not
        # the controlling reviewer in review.
        principal = self._principal()
        if ownership.can_edit_work_item(obj, principal):
            return False
        if ownership.can_review_work_item(obj, principal):
            return False
        return True

    def get_can_edit(self, obj):
        return ownership.can_edit_work_item(obj, self._principal())

    def get_can_submit_for_review(self, obj):
        return ownership.can_submit_for_review(obj, self._principal())

    def get_can_review(self, obj):
        return ownership.can_review_work_item(obj, self._principal())

    def get_can_upload_internal(self, obj):
        return ownership.can_upload_internal(
            obj,
            self._principal(),
        )

    @staticmethod
    def _document_readiness(obj):
        cache_name = "_vridhi_document_readiness"

        if not hasattr(obj, cache_name):
            setattr(
                obj,
                cache_name,
                calculate_document_readiness(obj),
            )

        return getattr(obj, cache_name)

    def get_document_ready(self, obj):
        return self._document_readiness(obj)[
            "ready_for_review"
        ]

    def get_document_readiness_state(self, obj):
        return self._document_readiness(obj)[
            "readiness_state"
        ]

    def get_document_health_score(self, obj):
        return self._document_readiness(obj)[
            "health_score"
        ]

    def get_mandatory_document_total(self, obj):
        return self._document_readiness(obj)[
            "mandatory_total"
        ]

    def get_mandatory_document_satisfied(self, obj):
        return self._document_readiness(obj)[
            "mandatory_satisfied"
        ]

    def get_mandatory_document_missing(self, obj):
        return self._document_readiness(obj)[
            "mandatory_missing"
        ]

    def get_document_blockers(self, obj):
        return self._document_readiness(obj)[
            "blockers"
        ]


class WorkNoteSerializer(serializers.ModelSerializer):
    author_name = serializers.SerializerMethodField()

    class Meta:
        model = WorkNote
        fields = "__all__"
        read_only_fields = _AUDIT

    @staticmethod
    def get_author_name(obj):
        if not obj.author_user_id:
            return ""
        emp = Employee.objects.filter(tenant_id=obj.tenant_id, id=obj.author_user_id).first()
        return emp.name if emp else ""


class DocumentRequestSerializer(serializers.ModelSerializer):
    client_name = serializers.SerializerMethodField()
    requested_from_name = serializers.SerializerMethodField()
    attachment_count = serializers.SerializerMethodField()
    accepted_attachment_count = serializers.SerializerMethodField()
    pending_review_count = serializers.SerializerMethodField()
    latest_version = serializers.SerializerMethodField()
    is_expired = serializers.SerializerMethodField()
    days_to_expiry = serializers.SerializerMethodField()

    class Meta:
        model = DocumentRequest
        fields = "__all__"
        read_only_fields = (
            *_AUDIT,
            "received_date",
            "sent_at",
            "verified_at",
            "verified_by",
            "verification_comment",
            "status",
            "source_requirement_set_id",
            "source_requirement_id",
            "auto_generated",
        )

    @staticmethod
    def get_client_name(obj):
        client = Client.objects.filter(tenant_id=obj.tenant_id, id=obj.client_id).first()
        return (client.trade_name or client.legal_name) if client else ""

    @staticmethod
    def get_requested_from_name(obj):
        if not obj.requested_from_contact_id:
            return ""
        contact = ClientContact.objects.filter(tenant_id=obj.tenant_id, id=obj.requested_from_contact_id).first()
        return contact.name if contact else ""

    @staticmethod
    def get_attachment_count(obj):
        return DocumentAttachment.objects.filter(
            tenant_id=obj.tenant_id,
            document_request_id=obj.id,
        ).count()

    @staticmethod
    def get_accepted_attachment_count(obj):
        return DocumentAttachment.objects.filter(
            tenant_id=obj.tenant_id,
            document_request_id=obj.id,
            review_status="ACCEPTED",
        ).count()

    @staticmethod
    def get_pending_review_count(obj):
        return DocumentAttachment.objects.filter(
            tenant_id=obj.tenant_id,
            document_request_id=obj.id,
            review_status="PENDING_REVIEW",
        ).count()

    @staticmethod
    def get_latest_version(obj):
        latest = (
            DocumentAttachment.objects.filter(
                tenant_id=obj.tenant_id,
                document_request_id=obj.id,
            )
            .order_by("-version_number", "-created_at", "-id")
            .first()
        )
        return latest.version_number if latest else 0

    @staticmethod
    def get_is_expired(obj):
        return bool(obj.expires_on and obj.expires_on < date.today())

    @staticmethod
    def get_days_to_expiry(obj):
        if not obj.expires_on:
            return None
        return (obj.expires_on - date.today()).days


class DocumentAttachmentSerializer(serializers.ModelSerializer):
    download_url = serializers.SerializerMethodField()
    reviewed_by_name = serializers.SerializerMethodField()

    class Meta:
        model = DocumentAttachment
        fields = (
            "id",
            "document_request_id",
            "work_item_id",
            "source",
            "uploaded_by",
            "original_name",
            "content_type",
            "size_bytes",
            "sha256",
            "version_number",
            "version_label",
            "supersedes_attachment_id",
            "duplicate_of_attachment_id",
            "is_duplicate",
            "review_status",
            "reviewed_at",
            "reviewed_by",
            "reviewed_by_name",
            "review_comment",
            "download_url",
            "created_at",
        )
        read_only_fields = fields

    def get_download_url(self, obj):
        return f"/api/v1/document-attachments/{obj.id}/download/"

    @staticmethod
    def get_reviewed_by_name(obj):
        if not obj.reviewed_by:
            return ""
        employee = Employee.objects.filter(
            tenant_id=obj.tenant_id,
            principal_id=obj.reviewed_by,
        ).first()
        return employee.name if employee else ""
