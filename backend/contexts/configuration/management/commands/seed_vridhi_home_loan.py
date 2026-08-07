from __future__ import annotations

from uuid import UUID

from django.core.management import call_command
from django.core.management.base import (
    BaseCommand,
    CommandError,
)
from django.db import transaction

from contexts.configuration.models import (
    CatalogueStatus,
    Domain,
    Service,
    ServiceDocumentRequirement,
    ServiceDocumentRequirementSet,
    ServiceOperationalField,
    Vertical,
)


DOMAIN_CODE = "LOAN_SERVICES"
SERVICE_CODE = "HOME_LOAN"


OPERATIONAL_FIELDS = (
    {
        "field_key": "requested_loan_amount",
        "label": "Requested Loan Amount",
        "field_type": "NUMBER",
        "is_required": True,
        "display_order": 10,
    },
    {
        "field_key": "applicant_type",
        "label": "Applicant Type",
        "field_type": "TEXT",
        "is_required": True,
        "display_order": 20,
    },
    {
        "field_key": "employment_type",
        "label": "Employment Type",
        "field_type": "TEXT",
        "is_required": True,
        "display_order": 30,
    },
    {
        "field_key": "property_type",
        "label": "Property Type",
        "field_type": "TEXT",
        "is_required": True,
        "display_order": 40,
    },
    {
        "field_key": "property_location",
        "label": "Property Location",
        "field_type": "TEXT",
        "is_required": True,
        "display_order": 50,
    },
    {
        "field_key": "preferred_lender",
        "label": "Preferred Bank / Lender",
        "field_type": "TEXT",
        "is_required": False,
        "display_order": 60,
    },
    {
        "field_key": "existing_monthly_emi",
        "label": "Existing Monthly EMI",
        "field_type": "NUMBER",
        "is_required": False,
        "display_order": 70,
    },
)


DOCUMENT_REQUIREMENTS = (
    {
        "code": "PAN_CARD",
        "name": "PAN Card",
        "description": "PAN card of the applicant.",
        "category": "IDENTITY_KYC",
        "mandatory": True,
        "display_order": 10,
    },
    {
        "code": "AADHAAR_CARD",
        "name": "Aadhaar Card",
        "description": "Aadhaar card of the applicant.",
        "category": "IDENTITY_KYC",
        "mandatory": True,
        "display_order": 20,
    },
    {
        "code": "PHOTOGRAPH",
        "name": "Applicant Photograph",
        "description": "Recent applicant photograph.",
        "category": "IDENTITY_KYC",
        "mandatory": True,
        "display_order": 30,
    },
    {
        "code": "BANK_STATEMENTS",
        "name": "Bank Statements",
        "description": (
            "Recent bank statements required for loan assessment."
        ),
        "category": "BANKING",
        "mandatory": True,
        "display_order": 40,
    },
    {
        "code": "INCOME_PROOF",
        "name": "Income Proof",
        "description": (
            "Salary slips, ITR or other applicable income proof."
        ),
        "category": "OTHER",
        "mandatory": True,
        "display_order": 50,
    },
    {
        "code": "ADDRESS_PROOF",
        "name": "Address Proof",
        "description": "Current residential address proof.",
        "category": "IDENTITY_KYC",
        "mandatory": True,
        "display_order": 60,
    },
    {
        "code": "PROPERTY_DOCUMENTS",
        "name": "Property Documents",
        "description": (
            "Available property ownership / transaction documents."
        ),
        "category": "OTHER",
        "mandatory": True,
        "display_order": 70,
    },
    {
        "code": "EMPLOYMENT_BUSINESS_PROOF",
        "name": "Employment / Business Proof",
        "description": (
            "Employment or business proof applicable to the applicant."
        ),
        "category": "OTHER",
        "mandatory": True,
        "display_order": 80,
    },
)


def _operational_payload(definition):
    return {
        "label": definition["label"],
        "field_type": definition["field_type"],
        "help_text": "",
        "placeholder": "",
        "required": definition["is_required"],
        "options": [],
        "display_order": definition["display_order"],
        "is_active": True,
    }

def _active_requirement_status():
    field = ServiceDocumentRequirementSet._meta.get_field(
        "status"
    )

    choices = {
        str(value)
        for value, _label in (field.choices or ())
    }

    if "ACTIVE" not in choices:
        raise CommandError(
            "Requirement-set model does not expose ACTIVE status. "
            f"Available values: {sorted(choices)}"
        )

    return "ACTIVE"


class Command(BaseCommand):
    help = (
        "Seed the first approved Vridhi operational business "
        "configuration: Loans -> Loan Services -> Home Loan."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--tenant-id",
            required=True,
            help="Tenant UUID for Vridhi Consultants.",
        )
        parser.add_argument(
            "--principal-id",
            required=True,
            help=(
                "Principal UUID recorded in catalogue "
                "audit ownership fields."
            ),
        )

    @transaction.atomic
    def handle(self, *args, **options):
        try:
            tenant_id = UUID(options["tenant_id"])
        except (TypeError, ValueError) as exc:
            raise CommandError(
                "tenant-id must be a valid UUID."
            ) from exc

        try:
            principal_id = UUID(options["principal_id"])
        except (TypeError, ValueError) as exc:
            raise CommandError(
                "principal-id must be a valid UUID."
            ) from exc

        # Reuse the approved Vridhi vertical seed mechanism.
        call_command(
            "seed_vridhi_verticals",
            tenant_id=str(tenant_id),
            principal_id=str(principal_id),
            verbosity=0,
        )

        loans = Vertical.objects.get(
            tenant_id=tenant_id,
            code="LOANS",
        )

        domain, domain_created = Domain.objects.get_or_create(
            tenant_id=tenant_id,
            vertical_id=loans.id,
            code=DOMAIN_CODE,
            defaults={
                "created_by": principal_id,
                "updated_by": principal_id,
                "name": "Loan Services",
                "description": (
                    "Loan application, assessment and "
                    "documentation services."
                ),
                "status": CatalogueStatus.ACTIVE,
            },
        )

        domain_updates = []

        if domain.name != "Loan Services":
            domain.name = "Loan Services"
            domain_updates.append("name")

        if not domain.description:
            domain.description = (
                "Loan application, assessment and "
                "documentation services."
            )
            domain_updates.append("description")

        if domain.status != CatalogueStatus.ACTIVE:
            domain.status = CatalogueStatus.ACTIVE
            domain_updates.append("status")

        if domain_updates:
            domain.updated_by = principal_id
            domain_updates.extend(
                ["updated_by", "updated_at"]
            )
            domain.save(update_fields=domain_updates)

        service, service_created = Service.objects.get_or_create(
            tenant_id=tenant_id,
            domain_id=domain.id,
            code=SERVICE_CODE,
            defaults={
                "created_by": principal_id,
                "updated_by": principal_id,
                "name": "Home Loan",
                "description": (
                    "Home loan application, documentation "
                    "and processing."
                ),
                "status": CatalogueStatus.ACTIVE,
            },
        )

        service_updates = []

        if service.name != "Home Loan":
            service.name = "Home Loan"
            service_updates.append("name")

        if not service.description:
            service.description = (
                "Home loan application, documentation "
                "and processing."
            )
            service_updates.append("description")

        if service.status != CatalogueStatus.ACTIVE:
            service.status = CatalogueStatus.ACTIVE
            service_updates.append("status")

        if service_updates:
            service.updated_by = principal_id
            service_updates.extend(
                ["updated_by", "updated_at"]
            )
            service.save(update_fields=service_updates)

        operational_created = 0
        operational_existing = 0

        for definition in OPERATIONAL_FIELDS:
            payload = _operational_payload(definition)

            update_defaults = {
                **payload,
                "updated_by": principal_id,
            }

            create_defaults = {
                **payload,
                "created_by": principal_id,
                "updated_by": principal_id,
            }

            _field, created = (
                ServiceOperationalField.objects.update_or_create(
                    tenant_id=tenant_id,
                    service_id=service.id,
                    key=definition["field_key"],
                    defaults=update_defaults,
                    create_defaults=create_defaults,
                )
            )

            if created:
                operational_created += 1
            else:
                operational_existing += 1

        requirement_set, requirement_set_created = (
            ServiceDocumentRequirementSet.objects.get_or_create(
                tenant_id=tenant_id,
                service_id=service.id,
                version_number=1,
                defaults={
                    "created_by": principal_id,
                    "updated_by": principal_id,
                    "name": "Home Loan Document Checklist",
                    "status": _active_requirement_status(),
                    "description": (
                        "Initial Vridhi Home Loan document "
                        "checklist."
                    ),
                },
            )
        )

        requirement_set_updates = []

        if (
            requirement_set.name
            != "Home Loan Document Checklist"
        ):
            requirement_set.name = (
                "Home Loan Document Checklist"
            )
            requirement_set_updates.append("name")

        if requirement_set.status != "ACTIVE":
            requirement_set.status = "ACTIVE"
            requirement_set_updates.append("status")

        if not requirement_set.description:
            requirement_set.description = (
                "Initial Vridhi Home Loan document checklist."
            )
            requirement_set_updates.append("description")

        if requirement_set_updates:
            requirement_set.updated_by = principal_id
            requirement_set_updates.extend(
                ["updated_by", "updated_at"]
            )
            requirement_set.save(
                update_fields=requirement_set_updates
            )

        requirement_created = 0
        requirement_existing = 0

        for definition in DOCUMENT_REQUIREMENTS:
            business_defaults = {
                "service_id": service.id,
                "name": definition["name"],
                "description": definition["description"],
                "category": definition["category"],
                "mandatory": definition["mandatory"],
                "display_order": definition["display_order"],
                "is_active": True,
            }

            update_defaults = {
                **business_defaults,
                "updated_by": principal_id,
            }

            create_defaults = {
                **business_defaults,
                "created_by": principal_id,
                "updated_by": principal_id,
            }

            _requirement, created = (
                ServiceDocumentRequirement.objects.update_or_create(
                    tenant_id=tenant_id,
                    requirement_set_id=requirement_set.id,
                    code=definition["code"],
                    defaults=update_defaults,
                    create_defaults=create_defaults,
                )
            )

            if created:
                requirement_created += 1
            else:
                requirement_existing += 1

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                "VRIDHI_HOME_LOAN_SEED=PASS"
            )
        )

        self.stdout.write(
            "Hierarchy: Loans -> Loan Services -> Home Loan"
        )

        self.stdout.write(
            "Domain: "
            + (
                "created"
                if domain_created
                else "existing"
            )
        )

        self.stdout.write(
            "Service: "
            + (
                "created"
                if service_created
                else "existing"
            )
        )

        self.stdout.write(
            "Operational fields: "
            f"created={operational_created}, "
            f"updated/existing={operational_existing}"
        )

        self.stdout.write(
            "Requirement set: "
            + (
                "created"
                if requirement_set_created
                else "existing"
            )
        )

        self.stdout.write(
            "Document requirements: "
            f"created={requirement_created}, "
            f"updated/existing={requirement_existing}"
        )
