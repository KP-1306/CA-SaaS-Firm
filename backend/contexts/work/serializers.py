from __future__ import annotations

from datetime import date

from rest_framework import serializers

from contexts.clients.models import Client, ClientContact
from contexts.configuration.models import (
    Domain,
    Service,
    ServiceOperationalField,
    ServiceProcessStep,
)
from contexts.identity.models import Employee


# ---------------------------------------------------------------------------
# Udyam process-owned lifecycle evidence keys.
#
# These keys are written ONLY by dedicated Udyam business actions
# (udyam-submit-application, udyam-report-query, udyam-resolve-query,
# udyam-complete-registration).  They are NOT user-configurable
# ServiceOperationalField values.  Generic Work create/update must never
# manufacture, overwrite or erase them; for these keys the database instance
# is authoritative.
#
# This ownership constant is defined here, in the persistence layer that
# enforces it, so the persistence contract does not depend on the monitoring /
# observability subsystem.
# ---------------------------------------------------------------------------
UDYAM_PROCESS_OWNED_KEYS = frozenset(
    {
        "udyam_application_reference",
        "udyam_submission_date",
        "udyam_submission_time",
        "udyam_query_type",
        "udyam_query_remarks",
        "udyam_query_resolution_remarks",
        "udyam_certificate_attachment_id",
    }
)

_UDYAM_SERVICE_CODE = "UDYAM_REGISTRATION"

from . import ownership
from .document_intelligence import calculate_document_readiness
from .models import (
    DocumentAttachment,
    DocumentRequest,
    WorkItem,
    WorkNote,
    WorkProcessState,
)

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

    # Display-only status. Generic WorkItem.status remains the
    # authoritative lifecycle/control status.
    effective_status = serializers.SerializerMethodField()

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

    def _effective_status_context(self, tenant_id):
        cache_name = (
            "_vridhi_effective_status_context_"
            f"{tenant_id}"
        )

        if not hasattr(self, cache_name):
            service_codes = {
                row.id: row.code
                for row in Service.objects.filter(
                    tenant_id=tenant_id,
                ).only(
                    "id",
                    "code",
                )
            }

            process_states = {
                row.work_item_id: row.current_step_id
                for row in WorkProcessState.objects.filter(
                    tenant_id=tenant_id,
                ).only(
                    "work_item_id",
                    "current_step_id",
                )
            }

            process_steps = {
                row.id: {
                    "code": row.code,
                    "name": row.name,
                }
                for row in ServiceProcessStep.objects.filter(
                    tenant_id=tenant_id,
                    is_active=True,
                ).only(
                    "id",
                    "code",
                    "name",
                )
            }

            setattr(
                self,
                cache_name,
                (
                    service_codes,
                    process_states,
                    process_steps,
                ),
            )

        return getattr(self, cache_name)

    def get_effective_status(self, obj):
        raw_status = str(obj.status or "")

        if not obj.service_id:
            return raw_status

        (
            service_codes,
            process_states,
            process_steps,
        ) = self._effective_status_context(
            obj.tenant_id,
        )

        # Both UDYAM_REGISTRATION and MUDRA_LOAN use this same generic,
        # already service-agnostic mechanism below (WorkProcessState +
        # ServiceProcessStep name lookup) to display the durable business
        # stage once the generic control states no longer apply. Every
        # other service is unaffected and still returns raw_status here.
        if (
            service_codes.get(obj.service_id)
            not in ("UDYAM_REGISTRATION", "MUDRA_LOAN")
        ):
            return raw_status

        # Generic workflow control states remain authoritative.
        # Do not disguise review/rework/waiting semantics with
        # a service-process label.
        if raw_status in {
            "WAITING_FOR_CLIENT",
            "READY_FOR_REVIEW",
            "REWORK_REQUIRED",
            "CANCELLED",
        }:
            return raw_status

        current_step_id = process_states.get(obj.id)

        if not current_step_id:
            return raw_status

        current_step = process_steps.get(current_step_id)

        if not current_step:
            return raw_status

        process_name = str(
            current_step.get("name") or ""
        ).strip()

        return process_name or raw_status

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


    def _is_udyam_service(self, service_id) -> bool:
        """True only for the configured Udyam registration service."""
        if not service_id:
            return False
        return Service.objects.filter(
            tenant_id=self._tenant(),
            id=service_id,
            code=_UDYAM_SERVICE_CODE,
        ).exists()

    def validate(self, attrs):
        attrs = super().validate(attrs)

        instance = getattr(self, "instance", None)

        service_id = attrs.get(
            "service_id",
            getattr(instance, "service_id", None),
        )

        # Non-Udyam services keep the EXACT original behaviour: the supplied
        # operational_data (or the instance's, when not supplied) is validated
        # and rebuilt against the configured ServiceOperationalField set.
        if not self._is_udyam_service(service_id):
            operational_data = attrs.get(
                "operational_data",
                getattr(instance, "operational_data", {}),
            )
            attrs["operational_data"] = self._validate_operational_data(
                service_id,
                operational_data,
            )
            return attrs

        # Udyam service: protect process-owned lifecycle evidence.  The
        # database instance is authoritative for the reserved keys; generic
        # saves may only touch normal configured fields.
        current_data = dict(getattr(instance, "operational_data", None) or {})
        preserved_evidence = {
            key: current_data[key]
            for key in UDYAM_PROCESS_OWNED_KEYS
            if key in current_data
        }

        if "operational_data" in attrs:
            # A generic save supplied operational_data.  Ignore any incoming
            # values for reserved keys (never trust the browser), validate the
            # normal fields exactly as usual, then re-apply authoritative
            # evidence from the database.
            incoming = dict(attrs.get("operational_data") or {})
            normal_incoming = {
                key: value
                for key, value in incoming.items()
                if key not in UDYAM_PROCESS_OWNED_KEYS
            }
            validated_normal = self._validate_operational_data(
                service_id,
                normal_incoming,
            )
            attrs["operational_data"] = {**validated_normal, **preserved_evidence}
        else:
            # No operational_data supplied.  Validate the instance's normal
            # fields (unchanged behaviour) and re-apply authoritative evidence.
            existing_normal = {
                key: value
                for key, value in current_data.items()
                if key not in UDYAM_PROCESS_OWNED_KEYS
            }
            validated_normal = self._validate_operational_data(
                service_id,
                existing_normal,
            )
            attrs["operational_data"] = {**validated_normal, **preserved_evidence}

        return attrs

    def _validate_operational_data(
        self,
        service_id,
        operational_data,
    ):
        if operational_data in (None, ""):
            operational_data = {}

        if not isinstance(operational_data, dict):
            raise serializers.ValidationError(
                {
                    "operational_data": (
                        "Operational values must be supplied as an object."
                    )
                }
            )

        if not service_id:
            if operational_data:
                raise serializers.ValidationError(
                    {
                        "operational_data": (
                            "Operational values require a selected service."
                        )
                    }
                )

            return {}

        fields = list(
            ServiceOperationalField.objects.filter(
                tenant_id=self._tenant(),
                service_id=service_id,
                is_active=True,
            ).order_by(
                "display_order",
                "label",
                "id",
            )
        )

        definitions = {
            field.key: field
            for field in fields
        }

        unknown = sorted(
            set(operational_data) - set(definitions)
        )

        if unknown:
            raise serializers.ValidationError(
                {
                    "operational_data": (
                        "Unknown operational field(s): "
                        + ", ".join(unknown)
                    )
                }
            )

        cleaned = {}

        for field in fields:
            supplied = field.key in operational_data
            value = operational_data.get(field.key)

            if value is None:
                value = ""

            if (
                field.required
                and (
                    not supplied
                    or value == ""
                    or value == []
                )
            ):
                raise serializers.ValidationError(
                    {
                        "operational_data": {
                            field.key: (
                                f"{field.label} is required."
                            )
                        }
                    }
                )

            if not supplied or value == "":
                continue

            if field.field_type in ("TEXT", "LONG_TEXT"):
                cleaned[field.key] = str(value).strip()

            elif field.field_type == "NUMBER":
                if isinstance(value, bool):
                    raise serializers.ValidationError(
                        {
                            "operational_data": {
                                field.key: (
                                    f"{field.label} must be a number."
                                )
                            }
                        }
                    )

                try:
                    cleaned[field.key] = float(value)
                except (TypeError, ValueError):
                    raise serializers.ValidationError(
                        {
                            "operational_data": {
                                field.key: (
                                    f"{field.label} must be a number."
                                )
                            }
                        }
                    )

            elif field.field_type == "BOOLEAN":
                if not isinstance(value, bool):
                    raise serializers.ValidationError(
                        {
                            "operational_data": {
                                field.key: (
                                    f"{field.label} must be Yes or No."
                                )
                            }
                        }
                    )

                cleaned[field.key] = value

            elif field.field_type == "DATE":
                date_field = serializers.DateField()

                try:
                    cleaned[field.key] = (
                        date_field.to_internal_value(value).isoformat()
                    )
                except serializers.ValidationError:
                    raise serializers.ValidationError(
                        {
                            "operational_data": {
                                field.key: (
                                    f"{field.label} must be a valid date."
                                )
                            }
                        }
                    )

            elif field.field_type == "SELECT":
                text = str(value).strip()

                if text not in field.options:
                    raise serializers.ValidationError(
                        {
                            "operational_data": {
                                field.key: (
                                    f"Select a valid value for "
                                    f"{field.label}."
                                )
                            }
                        }
                    )

                cleaned[field.key] = text

        return cleaned


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
    # Preserve the established standalone request contract.
    #
    # The model field is nullable, but its conditional uniqueness
    # constraint can cause ModelSerializer field inference to mark it
    # as required. Declare it explicitly so requests may remain
    # standalone while supplied UUID values still receive normal DRF
    # validation.
    work_item_id = serializers.UUIDField(
        required=False,
        allow_null=True,
    )

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
            "duplicate_resolution",
            "is_canonical",
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
