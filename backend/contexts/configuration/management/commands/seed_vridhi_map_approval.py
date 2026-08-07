from __future__ import annotations

from uuid import UUID

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
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


DOMAINS = {
    "BUILDING_MAP_APPROVALS": {
        "name": "Building & Map Approvals",
        "description": (
            "Residential, commercial and layout map "
            "preparation / approval work."
        ),
    },
    "COMPLETION_REGULARIZATION": {
        "name": "Completion & Regularization",
        "description": (
            "Completion, regularization and related "
            "building approval work."
        ),
    },
}


SERVICES = {
    "RESIDENTIAL_MAP_APPROVAL": {
        "domain": "BUILDING_MAP_APPROVALS",
        "name": "Residential Map Approval",
        "description": (
            "Residential building map preparation "
            "and approval processing."
        ),
        "fields": (
            (
                "property_owner_name",
                "Property Owner Name",
                "TEXT",
                True,
                [],
                10,
            ),
            (
                "property_address",
                "Property Address",
                "LONG_TEXT",
                True,
                [],
                20,
            ),
            (
                "plot_area",
                "Plot Area",
                "NUMBER",
                True,
                [],
                30,
            ),
            (
                "proposed_builtup_area",
                "Proposed Built-up Area",
                "NUMBER",
                False,
                [],
                40,
            ),
            (
                "number_of_floors",
                "Number of Floors",
                "NUMBER",
                True,
                [],
                50,
            ),
            (
                "development_authority",
                "Development Authority / Local Body",
                "TEXT",
                False,
                [],
                60,
            ),
            (
                "property_use",
                "Property Use",
                "SELECT",
                True,
                [
                    "Self Residential",
                    "Rental Residential",
                    "Residential Building",
                    "Other",
                ],
                70,
            ),
            (
                "case_notes",
                "Map Approval Notes",
                "LONG_TEXT",
                False,
                [],
                80,
            ),
        ),
        "documents": (
            (
                "OWNER_IDENTITY",
                "Owner Identity Proof",
                "Identity proof of property owner.",
                "IDENTITY_KYC",
                True,
                10,
            ),
            (
                "OWNER_PAN",
                "Owner PAN",
                "PAN of property owner.",
                "IDENTITY_KYC",
                True,
                20,
            ),
            (
                "OWNERSHIP_DOCUMENT",
                "Property Ownership Document",
                "Applicable ownership / title document.",
                "OTHER",
                True,
                30,
            ),
            (
                "LAND_RECORD",
                "Land / Revenue Record",
                "Applicable land or revenue record.",
                "OTHER",
                True,
                40,
            ),
            (
                "SITE_PLAN",
                "Existing Site / Plot Plan",
                "Existing site or plot details where available.",
                "OTHER",
                False,
                50,
            ),
            (
                "PROPERTY_TAX_RECORD",
                "Property Tax / Local Body Record",
                "Applicable tax or local-body record.",
                "OTHER",
                False,
                60,
            ),
            (
                "NOC_SUPPORTING",
                "Applicable NOC / Supporting Approval",
                "NOC or related approval where applicable.",
                "OTHER",
                False,
                70,
            ),
        ),
    },

    "COMMERCIAL_MAP_APPROVAL": {
        "domain": "BUILDING_MAP_APPROVALS",
        "name": "Commercial Map Approval",
        "description": (
            "Commercial building map preparation "
            "and approval processing."
        ),
        "fields": (
            (
                "property_owner_name",
                "Property Owner / Entity Name",
                "TEXT",
                True,
                [],
                10,
            ),
            (
                "property_address",
                "Property Address",
                "LONG_TEXT",
                True,
                [],
                20,
            ),
            (
                "plot_area",
                "Plot Area",
                "NUMBER",
                True,
                [],
                30,
            ),
            (
                "proposed_builtup_area",
                "Proposed Built-up Area",
                "NUMBER",
                True,
                [],
                40,
            ),
            (
                "number_of_floors",
                "Number of Floors",
                "NUMBER",
                True,
                [],
                50,
            ),
            (
                "commercial_use",
                "Proposed Commercial Use",
                "TEXT",
                True,
                [],
                60,
            ),
            (
                "development_authority",
                "Development Authority / Local Body",
                "TEXT",
                False,
                [],
                70,
            ),
            (
                "case_notes",
                "Map Approval Notes",
                "LONG_TEXT",
                False,
                [],
                80,
            ),
        ),
        "documents": (
            (
                "OWNER_ENTITY_ID",
                "Owner / Entity Identity Proof",
                "Applicable identity proof.",
                "IDENTITY_KYC",
                True,
                10,
            ),
            (
                "OWNER_ENTITY_PAN",
                "Owner / Entity PAN",
                "Applicable PAN.",
                "IDENTITY_KYC",
                True,
                20,
            ),
            (
                "OWNERSHIP_DOCUMENT",
                "Property Ownership Document",
                "Applicable title or ownership document.",
                "OTHER",
                True,
                30,
            ),
            (
                "LAND_RECORD",
                "Land / Revenue Record",
                "Applicable land/revenue record.",
                "OTHER",
                True,
                40,
            ),
            (
                "SITE_PLAN",
                "Existing Site / Plot Plan",
                "Available existing property plan.",
                "OTHER",
                False,
                50,
            ),
            (
                "ENTITY_PROOF",
                "Business / Entity Proof",
                "Applicable business constitution proof.",
                "OTHER",
                False,
                60,
            ),
            (
                "NOC_SUPPORTING",
                "Applicable NOCs / Supporting Approvals",
                "Additional approvals where applicable.",
                "OTHER",
                False,
                70,
            ),
            (
                "UTILITY_PROPERTY_RECORD",
                "Utility / Property Record",
                "Supporting local property record where applicable.",
                "OTHER",
                False,
                80,
            ),
        ),
    },

    "LAYOUT_APPROVAL": {
        "domain": "BUILDING_MAP_APPROVALS",
        "name": "Layout Approval",
        "description": (
            "Plotting, site-layout and layout approval processing."
        ),
        "fields": (
            (
                "owner_developer_name",
                "Owner / Developer Name",
                "TEXT",
                True,
                [],
                10,
            ),
            (
                "site_location",
                "Site Location",
                "LONG_TEXT",
                True,
                [],
                20,
            ),
            (
                "total_land_area",
                "Total Land Area",
                "NUMBER",
                True,
                [],
                30,
            ),
            (
                "proposed_plot_count",
                "Proposed Number of Plots",
                "NUMBER",
                False,
                [],
                40,
            ),
            (
                "layout_use",
                "Layout Use",
                "SELECT",
                True,
                [
                    "Residential",
                    "Commercial",
                    "Mixed",
                    "Other",
                ],
                50,
            ),
            (
                "development_authority",
                "Development Authority / Local Body",
                "TEXT",
                False,
                [],
                60,
            ),
            (
                "layout_notes",
                "Layout Approval Notes",
                "LONG_TEXT",
                False,
                [],
                70,
            ),
        ),
        "documents": (
            (
                "OWNER_IDENTITY",
                "Owner / Developer Identity Proof",
                "Applicable identity proof.",
                "IDENTITY_KYC",
                True,
                10,
            ),
            (
                "OWNERSHIP_DOCUMENTS",
                "Land Ownership Documents",
                "Applicable ownership/title documents.",
                "OTHER",
                True,
                20,
            ),
            (
                "LAND_RECORDS",
                "Land / Revenue Records",
                "Applicable revenue and land records.",
                "OTHER",
                True,
                30,
            ),
            (
                "SURVEY_SITE_PLAN",
                "Survey / Existing Site Plan",
                "Survey or site-plan information.",
                "OTHER",
                True,
                40,
            ),
            (
                "ACCESS_ROAD_DETAILS",
                "Access / Road Details",
                "Road and access supporting information.",
                "OTHER",
                False,
                50,
            ),
            (
                "NOC_SUPPORTING",
                "Applicable NOCs",
                "Additional NOC documents where applicable.",
                "OTHER",
                False,
                60,
            ),
        ),
    },

    "COMPLETION_CERTIFICATE": {
        "domain": "COMPLETION_REGULARIZATION",
        "name": "Completion Certificate",
        "description": (
            "Building completion certificate "
            "documentation and processing."
        ),
        "fields": (
            (
                "property_owner_name",
                "Property Owner Name",
                "TEXT",
                True,
                [],
                10,
            ),
            (
                "property_address",
                "Property Address",
                "LONG_TEXT",
                True,
                [],
                20,
            ),
            (
                "approved_map_reference",
                "Approved Map / Sanction Reference",
                "TEXT",
                True,
                [],
                30,
            ),
            (
                "completion_date",
                "Construction Completion Date",
                "DATE",
                False,
                [],
                40,
            ),
            (
                "constructed_floors",
                "Constructed Floors",
                "NUMBER",
                False,
                [],
                50,
            ),
            (
                "deviation_details",
                "Deviation / Change Details",
                "LONG_TEXT",
                False,
                [],
                60,
            ),
        ),
        "documents": (
            (
                "OWNER_IDENTITY",
                "Owner Identity Proof",
                "Identity proof of property owner.",
                "IDENTITY_KYC",
                True,
                10,
            ),
            (
                "OWNERSHIP_DOCUMENT",
                "Property Ownership Document",
                "Applicable ownership/title document.",
                "OTHER",
                True,
                20,
            ),
            (
                "APPROVED_MAP",
                "Approved / Sanctioned Map",
                "Previously approved building plan.",
                "OTHER",
                True,
                30,
            ),
            (
                "APPROVAL_LETTER",
                "Map Approval / Sanction Letter",
                "Relevant approval or sanction record.",
                "OTHER",
                True,
                40,
            ),
            (
                "COMPLETION_DRAWINGS",
                "Completion / As-Built Drawings",
                "Applicable completion drawings.",
                "OTHER",
                False,
                50,
            ),
            (
                "PROPERTY_LOCAL_RECORD",
                "Property / Local Body Record",
                "Relevant local property record.",
                "OTHER",
                False,
                60,
            ),
            (
                "NOC_SUPPORTING",
                "Applicable Completion NOCs",
                "NOCs/certificates where applicable.",
                "OTHER",
                False,
                70,
            ),
        ),
    },

    "BUILDING_REGULARIZATION": {
        "domain": "COMPLETION_REGULARIZATION",
        "name": "Building Regularization",
        "description": (
            "Existing building regularization "
            "documentation and approval processing."
        ),
        "fields": (
            (
                "property_owner_name",
                "Property Owner Name",
                "TEXT",
                True,
                [],
                10,
            ),
            (
                "property_address",
                "Property Address",
                "LONG_TEXT",
                True,
                [],
                20,
            ),
            (
                "plot_area",
                "Plot Area",
                "NUMBER",
                True,
                [],
                30,
            ),
            (
                "existing_builtup_area",
                "Existing Built-up Area",
                "NUMBER",
                False,
                [],
                40,
            ),
            (
                "existing_floors",
                "Existing Floors",
                "NUMBER",
                False,
                [],
                50,
            ),
            (
                "original_approval_available",
                "Original Approval Available",
                "BOOLEAN",
                True,
                [],
                60,
            ),
            (
                "deviation_regularization_scope",
                "Deviation / Regularization Scope",
                "LONG_TEXT",
                True,
                [],
                70,
            ),
            (
                "authority",
                "Development Authority / Local Body",
                "TEXT",
                False,
                [],
                80,
            ),
        ),
        "documents": (
            (
                "OWNER_IDENTITY",
                "Owner Identity Proof",
                "Identity proof of property owner.",
                "IDENTITY_KYC",
                True,
                10,
            ),
            (
                "OWNERSHIP_DOCUMENT",
                "Property Ownership Document",
                "Applicable ownership/title document.",
                "OTHER",
                True,
                20,
            ),
            (
                "LAND_RECORD",
                "Land / Revenue Record",
                "Applicable revenue record.",
                "OTHER",
                True,
                30,
            ),
            (
                "EXISTING_MAP",
                "Existing / Previous Map",
                "Existing drawing or prior approved map where available.",
                "OTHER",
                False,
                40,
            ),
            (
                "CURRENT_SITE_PLAN",
                "Current Site / Building Plan",
                "Current property/building plan.",
                "OTHER",
                True,
                50,
            ),
            (
                "LOCAL_PROPERTY_RECORD",
                "Local Property Record",
                "Property tax/local body supporting record.",
                "OTHER",
                False,
                60,
            ),
            (
                "NOTICE_ORDER",
                "Notice / Order / Authority Communication",
                "Any applicable authority communication.",
                "OTHER",
                False,
                70,
            ),
            (
                "NOC_SUPPORTING",
                "Applicable NOCs",
                "NOCs/supporting approvals where applicable.",
                "OTHER",
                False,
                80,
            ),
        ),
    },

    "OTHER_MAP_APPROVAL_WORK": {
        "domain": "COMPLETION_REGULARIZATION",
        "name": "Other Map Approval Work",
        "description": (
            "Property/map approval work not covered "
            "by a dedicated service."
        ),
        "fields": (
            (
                "work_type",
                "Map / Approval Work Type",
                "TEXT",
                True,
                [],
                10,
            ),
            (
                "property_address",
                "Property / Site Address",
                "LONG_TEXT",
                True,
                [],
                20,
            ),
            (
                "authority",
                "Development Authority / Local Body",
                "TEXT",
                False,
                [],
                30,
            ),
            (
                "target_date",
                "Target Date",
                "DATE",
                False,
                [],
                40,
            ),
            (
                "scope",
                "Requirement / Scope",
                "LONG_TEXT",
                True,
                [],
                50,
            ),
        ),
        "documents": (
            (
                "OWNER_IDENTITY",
                "Owner / Applicant Identity Proof",
                "Applicable identity proof.",
                "IDENTITY_KYC",
                True,
                10,
            ),
            (
                "PROPERTY_DOCUMENTS",
                "Property / Land Documents",
                "Relevant ownership or land documents.",
                "OTHER",
                True,
                20,
            ),
            (
                "EXISTING_APPROVALS",
                "Existing Maps / Approvals",
                "Existing approval records where available.",
                "OTHER",
                False,
                30,
            ),
            (
                "AUTHORITY_COMMUNICATION",
                "Authority Communication",
                "Any existing notice, letter or authority communication.",
                "OTHER",
                False,
                40,
            ),
            (
                "ADDITIONAL_DOCUMENTS",
                "Additional Supporting Documents",
                "Case-specific supporting documents.",
                "OTHER",
                False,
                50,
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


def _seed_domain(
    *,
    tenant_id,
    principal_id,
    vertical,
    code,
    definition,
):
    domain, _created = Domain.objects.get_or_create(
        tenant_id=tenant_id,
        vertical_id=vertical.id,
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
        domain,
        {
            "name": definition["name"],
            "description": definition["description"],
            "status": CatalogueStatus.ACTIVE,
        },
        principal_id,
    )

    return domain


def _seed_service(
    *,
    tenant_id,
    principal_id,
    domain,
    code,
    definition,
):
    service, _created = Service.objects.get_or_create(
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

    expected_keys = set()

    for (
        key,
        label,
        field_type,
        required,
        options,
        display_order,
    ) in definition["fields"]:

        expected_keys.add(key)

        values = {
            "label": label,
            "field_type": field_type,
            "help_text": "",
            "placeholder": "",
            "required": required,
            "options": options,
            "display_order": display_order,
            "is_active": True,
        }

        ServiceOperationalField.objects.update_or_create(
            tenant_id=tenant_id,
            service_id=service.id,
            key=key,
            defaults={
                **values,
                "updated_by": principal_id,
            },
            create_defaults={
                **values,
                "created_by": principal_id,
                "updated_by": principal_id,
            },
        )

    obsolete_fields = (
        ServiceOperationalField.objects.filter(
            tenant_id=tenant_id,
            service_id=service.id,
            is_active=True,
        ).exclude(
            key__in=expected_keys,
        )
    )

    for row in obsolete_fields:
        row.is_active = False
        row.updated_by = principal_id

        row.save(
            update_fields=[
                "is_active",
                "updated_by",
                "updated_at",
            ]
        )

    requirement_set, _created = (
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
                    f"Initial Vridhi {definition['name']} checklist."
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
                f"Initial Vridhi {definition['name']} checklist."
            ),
        },
        principal_id,
    )

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

        values = {
            "service_id": service.id,
            "name": name,
            "description": description,
            "category": category,
            "mandatory": mandatory,
            "display_order": display_order,
            "is_active": True,
        }

        ServiceDocumentRequirement.objects.update_or_create(
            tenant_id=tenant_id,
            requirement_set_id=requirement_set.id,
            code=req_code,
            defaults={
                **values,
                "updated_by": principal_id,
            },
            create_defaults={
                **values,
                "created_by": principal_id,
                "updated_by": principal_id,
            },
        )

    obsolete_requirements = (
        ServiceDocumentRequirement.objects.filter(
            tenant_id=tenant_id,
            requirement_set_id=requirement_set.id,
            is_active=True,
        ).exclude(
            code__in=expected_codes,
        )
    )

    for row in obsolete_requirements:
        row.is_active = False
        row.updated_by = principal_id

        row.save(
            update_fields=[
                "is_active",
                "updated_by",
                "updated_at",
            ]
        )

    return service


class Command(BaseCommand):
    help = (
        "Seed the approved Vridhi Map Approval "
        "operational catalogue."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--tenant-id",
            required=True,
        )

        parser.add_argument(
            "--principal-id",
            required=True,
        )

    @transaction.atomic
    def handle(self, *args, **options):
        try:
            tenant_id = UUID(options["tenant_id"])
            principal_id = UUID(options["principal_id"])
        except (TypeError, ValueError) as exc:
            raise CommandError(
                "tenant-id and principal-id must be valid UUIDs."
            ) from exc

        call_command(
            "seed_vridhi_verticals",
            tenant_id=str(tenant_id),
            principal_id=str(principal_id),
            verbosity=0,
        )

        vertical = Vertical.objects.get(
            tenant_id=tenant_id,
            code="MAP_APPROVAL",
        )

        domains = {
            code: _seed_domain(
                tenant_id=tenant_id,
                principal_id=principal_id,
                vertical=vertical,
                code=code,
                definition=definition,
            )
            for code, definition in DOMAINS.items()
        }

        for code, definition in SERVICES.items():
            _seed_service(
                tenant_id=tenant_id,
                principal_id=principal_id,
                domain=domains[definition["domain"]],
                code=code,
                definition=definition,
            )

        self.stdout.write("")

        self.stdout.write(
            self.style.SUCCESS(
                "VRIDHI_MAP_APPROVAL_SEED=PASS"
            )
        )

        self.stdout.write(
            f"Domains configured: {len(DOMAINS)}"
        )

        self.stdout.write(
            f"Services configured: {len(SERVICES)}"
        )
