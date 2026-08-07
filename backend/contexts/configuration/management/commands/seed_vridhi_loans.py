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


SERVICES = {
    "CAR_LOAN": {
        "name": "Car Loan",
        "description": (
            "New or used vehicle loan documentation and processing."
        ),
        "fields": (
            {
                "key": "requested_loan_amount",
                "label": "Requested Loan Amount",
                "field_type": "NUMBER",
                "required": True,
                "options": [],
                "display_order": 10,
            },
            {
                "key": "applicant_type",
                "label": "Applicant Type",
                "field_type": "SELECT",
                "required": True,
                "options": [
                    "Individual",
                    "Joint",
                    "Business",
                ],
                "display_order": 20,
            },
            {
                "key": "employment_type",
                "label": "Employment Type",
                "field_type": "SELECT",
                "required": True,
                "options": [
                    "Salaried",
                    "Self Employed",
                    "Business",
                    "Other",
                ],
                "display_order": 30,
            },
            {
                "key": "vehicle_condition",
                "label": "Vehicle Condition",
                "field_type": "SELECT",
                "required": True,
                "options": [
                    "New",
                    "Used",
                ],
                "display_order": 40,
            },
            {
                "key": "vehicle_make_model",
                "label": "Vehicle Make / Model",
                "field_type": "TEXT",
                "required": True,
                "options": [],
                "display_order": 50,
            },
            {
                "key": "vehicle_price",
                "label": "Vehicle / On-Road Price",
                "field_type": "NUMBER",
                "required": True,
                "options": [],
                "display_order": 60,
            },
            {
                "key": "preferred_lender",
                "label": "Preferred Bank / Lender",
                "field_type": "TEXT",
                "required": False,
                "options": [],
                "display_order": 70,
            },
            {
                "key": "existing_monthly_emi",
                "label": "Existing Monthly EMI",
                "field_type": "NUMBER",
                "required": False,
                "options": [],
                "display_order": 80,
            },
        ),
        "documents": (
            (
                "PAN_CARD",
                "PAN Card",
                "PAN card of the applicant.",
                "IDENTITY_KYC",
                True,
                10,
            ),
            (
                "AADHAAR_CARD",
                "Aadhaar Card",
                "Aadhaar card of the applicant.",
                "IDENTITY_KYC",
                True,
                20,
            ),
            (
                "PHOTOGRAPH",
                "Applicant Photograph",
                "Recent applicant photograph.",
                "IDENTITY_KYC",
                True,
                30,
            ),
            (
                "ADDRESS_PROOF",
                "Address Proof",
                "Current residential address proof.",
                "IDENTITY_KYC",
                True,
                40,
            ),
            (
                "BANK_STATEMENTS",
                "Bank Statements",
                "Recent bank statements for loan assessment.",
                "BANKING",
                True,
                50,
            ),
            (
                "INCOME_PROOF",
                "Income Proof",
                "Applicable salary, ITR or other income proof.",
                "OTHER",
                True,
                60,
            ),
            (
                "VEHICLE_QUOTATION",
                "Vehicle Quotation / Proforma Invoice",
                (
                    "Dealer quotation or other applicable "
                    "vehicle purchase document."
                ),
                "OTHER",
                True,
                70,
            ),
            (
                "EMPLOYMENT_BUSINESS_PROOF",
                "Employment / Business Proof",
                (
                    "Employment or business evidence applicable "
                    "to the applicant."
                ),
                "OTHER",
                True,
                80,
            ),
        ),
    },

    "MSME_LOAN": {
        "name": "MSME Loan",
        "description": (
            "MSME and small-business loan documentation "
            "and processing."
        ),
        "fields": (
            {
                "key": "requested_loan_amount",
                "label": "Requested Loan Amount",
                "field_type": "NUMBER",
                "required": True,
                "options": [],
                "display_order": 10,
            },
            {
                "key": "business_name",
                "label": "Business Name",
                "field_type": "TEXT",
                "required": True,
                "options": [],
                "display_order": 20,
            },
            {
                "key": "business_constitution",
                "label": "Business Constitution",
                "field_type": "SELECT",
                "required": True,
                "options": [
                    "Proprietorship",
                    "Partnership",
                    "LLP",
                    "Private Limited",
                    "Public Limited",
                    "Other",
                ],
                "display_order": 30,
            },
            {
                "key": "business_vintage_years",
                "label": "Business Vintage (Years)",
                "field_type": "NUMBER",
                "required": True,
                "options": [],
                "display_order": 40,
            },
            {
                "key": "annual_turnover",
                "label": "Approximate Annual Turnover",
                "field_type": "NUMBER",
                "required": True,
                "options": [],
                "display_order": 50,
            },
            {
                "key": "loan_purpose",
                "label": "Loan Purpose",
                "field_type": "LONG_TEXT",
                "required": True,
                "options": [],
                "display_order": 60,
            },
            {
                "key": "preferred_lender",
                "label": "Preferred Bank / Lender",
                "field_type": "TEXT",
                "required": False,
                "options": [],
                "display_order": 70,
            },
            {
                "key": "existing_business_loans",
                "label": "Existing Business Loan / EMI Details",
                "field_type": "LONG_TEXT",
                "required": False,
                "options": [],
                "display_order": 80,
            },
        ),
        "documents": (
            (
                "APPLICANT_PAN",
                "Applicant / Promoter PAN",
                "PAN of the relevant applicant or promoter.",
                "IDENTITY_KYC",
                True,
                10,
            ),
            (
                "APPLICANT_ID_PROOF",
                "Applicant / Promoter Identity Proof",
                "Applicable Aadhaar or other identity proof.",
                "IDENTITY_KYC",
                True,
                20,
            ),
            (
                "BUSINESS_REGISTRATION",
                "Business Registration / Constitution Proof",
                (
                    "Applicable incorporation, partnership, "
                    "registration or constitution proof."
                ),
                "OTHER",
                True,
                30,
            ),
            (
                "BUSINESS_ADDRESS_PROOF",
                "Business Address Proof",
                "Current business address proof.",
                "OTHER",
                True,
                40,
            ),
            (
                "BANK_STATEMENTS",
                "Business Bank Statements",
                (
                    "Recent business bank statements required "
                    "for assessment."
                ),
                "BANKING",
                True,
                50,
            ),
            (
                "FINANCIALS_ITR",
                "Financial Statements / ITR",
                (
                    "Applicable financial statements, income-tax "
                    "returns or financial records."
                ),
                "OTHER",
                True,
                60,
            ),
            (
                "GST_REGISTRATION",
                "GST Registration",
                "GST registration where applicable.",
                "OTHER",
                False,
                70,
            ),
            (
                "UDYAM_REGISTRATION",
                "Udyam Registration",
                "Udyam registration where applicable.",
                "OTHER",
                False,
                80,
            ),
            (
                "EXISTING_LOAN_STATEMENTS",
                "Existing Loan Statements",
                (
                    "Statements for existing business borrowings "
                    "where applicable."
                ),
                "BANKING",
                False,
                90,
            ),
        ),
    },

    "OTHER_LOAN": {
        "name": "Other Loan",
        "description": (
            "Generic loan workflow for loan products not "
            "covered by a dedicated service."
        ),
        "fields": (
            {
                "key": "loan_type_description",
                "label": "Loan Type / Product",
                "field_type": "TEXT",
                "required": True,
                "options": [],
                "display_order": 10,
            },
            {
                "key": "requested_loan_amount",
                "label": "Requested Loan Amount",
                "field_type": "NUMBER",
                "required": True,
                "options": [],
                "display_order": 20,
            },
            {
                "key": "applicant_type",
                "label": "Applicant Type",
                "field_type": "SELECT",
                "required": True,
                "options": [
                    "Individual",
                    "Joint",
                    "Business",
                    "Other",
                ],
                "display_order": 30,
            },
            {
                "key": "loan_purpose",
                "label": "Loan Purpose",
                "field_type": "LONG_TEXT",
                "required": True,
                "options": [],
                "display_order": 40,
            },
            {
                "key": "preferred_lender",
                "label": "Preferred Bank / Lender",
                "field_type": "TEXT",
                "required": False,
                "options": [],
                "display_order": 50,
            },
            {
                "key": "additional_details",
                "label": "Additional Loan Details",
                "field_type": "LONG_TEXT",
                "required": False,
                "options": [],
                "display_order": 60,
            },
        ),
        "documents": (
            (
                "PAN_CARD",
                "PAN Card",
                "PAN card of the applicant.",
                "IDENTITY_KYC",
                True,
                10,
            ),
            (
                "IDENTITY_PROOF",
                "Identity Proof",
                "Applicable applicant identity proof.",
                "IDENTITY_KYC",
                True,
                20,
            ),
            (
                "ADDRESS_PROOF",
                "Address Proof",
                "Current applicant address proof.",
                "IDENTITY_KYC",
                True,
                30,
            ),
            (
                "BANK_STATEMENTS",
                "Bank Statements",
                "Recent relevant bank statements.",
                "BANKING",
                True,
                40,
            ),
            (
                "INCOME_FINANCIAL_PROOF",
                "Income / Financial Proof",
                "Applicable income or financial proof.",
                "OTHER",
                True,
                50,
            ),
            (
                "LOAN_SUPPORTING_DOCUMENTS",
                "Loan-Specific Supporting Documents",
                (
                    "Additional documents required for the "
                    "selected loan product."
                ),
                "OTHER",
                False,
                60,
            ),
        ),
    },
}


def _update_audited(instance, values, principal_id):
    changed = []

    for field, value in values.items():
        if getattr(instance, field) != value:
            setattr(instance, field, value)
            changed.append(field)

    if not changed:
        return

    instance.updated_by = principal_id
    changed.extend(
        [
            "updated_by",
            "updated_at",
        ]
    )

    instance.save(update_fields=changed)


def _seed_service(
    *,
    tenant_id,
    principal_id,
    domain,
    code,
    definition,
):
    service, service_created = Service.objects.get_or_create(
        tenant_id=tenant_id,
        domain_id=domain.id,
        code=code,
        defaults={
            "created_by": principal_id,
            "updated_by": principal_id,
            "name": definition["name"],
            "description": definition["description"],
            "status": CatalogueStatus.ACTIVE,
        },
    )

    _update_audited(
        service,
        {
            "name": definition["name"],
            "description": definition["description"],
            "status": CatalogueStatus.ACTIVE,
        },
        principal_id,
    )

    field_created = 0
    field_existing = 0

    expected_keys = set()

    for field_definition in definition["fields"]:
        expected_keys.add(field_definition["key"])

        business_defaults = {
            "label": field_definition["label"],
            "field_type": field_definition["field_type"],
            "help_text": "",
            "placeholder": "",
            "required": field_definition["required"],
            "options": field_definition["options"],
            "display_order": field_definition["display_order"],
            "is_active": True,
        }

        field, created = (
            ServiceOperationalField.objects.update_or_create(
                tenant_id=tenant_id,
                service_id=service.id,
                key=field_definition["key"],
                defaults={
                    **business_defaults,
                    "updated_by": principal_id,
                },
                create_defaults={
                    **business_defaults,
                    "created_by": principal_id,
                    "updated_by": principal_id,
                },
            )
        )

        if created:
            field_created += 1
        else:
            field_existing += 1

    # Preserve historical rows but deactivate obsolete configured fields.
    obsolete_fields = ServiceOperationalField.objects.filter(
        tenant_id=tenant_id,
        service_id=service.id,
        is_active=True,
    ).exclude(
        key__in=expected_keys,
    )

    for field in obsolete_fields:
        field.is_active = False
        field.updated_by = principal_id
        field.save(
            update_fields=[
                "is_active",
                "updated_by",
                "updated_at",
            ]
        )

    requirement_set, set_created = (
        ServiceDocumentRequirementSet.objects.get_or_create(
            tenant_id=tenant_id,
            service_id=service.id,
            version_number=1,
            defaults={
                "created_by": principal_id,
                "updated_by": principal_id,
                "name": (
                    f"{definition['name']} Document Checklist"
                ),
                "status": "ACTIVE",
                "description": (
                    f"Initial Vridhi {definition['name']} "
                    "document checklist."
                ),
            },
        )
    )

    _update_audited(
        requirement_set,
        {
            "name": (
                f"{definition['name']} Document Checklist"
            ),
            "status": "ACTIVE",
            "description": (
                f"Initial Vridhi {definition['name']} "
                "document checklist."
            ),
        },
        principal_id,
    )

    requirement_created = 0
    requirement_existing = 0
    expected_codes = set()

    for (
        req_code,
        name,
        description,
        category,
        mandatory,
        display_order,
    ) in definition["documents"]:

        expected_codes.add(req_code)

        business_defaults = {
            "service_id": service.id,
            "name": name,
            "description": description,
            "category": category,
            "mandatory": mandatory,
            "display_order": display_order,
            "is_active": True,
        }

        requirement, created = (
            ServiceDocumentRequirement.objects.update_or_create(
                tenant_id=tenant_id,
                requirement_set_id=requirement_set.id,
                code=req_code,
                defaults={
                    **business_defaults,
                    "updated_by": principal_id,
                },
                create_defaults={
                    **business_defaults,
                    "created_by": principal_id,
                    "updated_by": principal_id,
                },
            )
        )

        if created:
            requirement_created += 1
        else:
            requirement_existing += 1

    obsolete_requirements = (
        ServiceDocumentRequirement.objects.filter(
            tenant_id=tenant_id,
            requirement_set_id=requirement_set.id,
            is_active=True,
        ).exclude(
            code__in=expected_codes,
        )
    )

    for requirement in obsolete_requirements:
        requirement.is_active = False
        requirement.updated_by = principal_id
        requirement.save(
            update_fields=[
                "is_active",
                "updated_by",
                "updated_at",
            ]
        )

    return {
        "service": service,
        "service_created": service_created,
        "field_created": field_created,
        "field_existing": field_existing,
        "set_created": set_created,
        "requirement_created": requirement_created,
        "requirement_existing": requirement_existing,
    }


class Command(BaseCommand):
    help = (
        "Seed the approved Vridhi Loans operational catalogue "
        "including Home Loan, Car Loan, MSME Loan and Other Loan."
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

        # Keep the already-certified Home Loan configuration canonical.
        call_command(
            "seed_vridhi_home_loan",
            tenant_id=str(tenant_id),
            principal_id=str(principal_id),
            verbosity=0,
        )

        loans = Vertical.objects.get(
            tenant_id=tenant_id,
            code="LOANS",
        )

        domain = Domain.objects.get(
            tenant_id=tenant_id,
            vertical_id=loans.id,
            code="LOAN_SERVICES",
        )

        results = {}

        for code, definition in SERVICES.items():
            results[code] = _seed_service(
                tenant_id=tenant_id,
                principal_id=principal_id,
                domain=domain,
                code=code,
                definition=definition,
            )

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                "VRIDHI_LOANS_SEED=PASS"
            )
        )

        self.stdout.write(
            "Hierarchy: Loans -> Loan Services"
        )

        self.stdout.write(
            "Services: Home Loan, Car Loan, MSME Loan, Other Loan"
        )

        for code, result in results.items():
            self.stdout.write(
                (
                    f"{code}: "
                    f"service_created="
                    f"{result['service_created']}, "
                    f"fields_created="
                    f"{result['field_created']}, "
                    f"fields_existing="
                    f"{result['field_existing']}, "
                    f"requirements_created="
                    f"{result['requirement_created']}, "
                    f"requirements_existing="
                    f"{result['requirement_existing']}"
                )
            )
