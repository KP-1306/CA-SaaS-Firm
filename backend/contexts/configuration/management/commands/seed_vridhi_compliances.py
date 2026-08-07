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
    "BUSINESS_REGISTRATIONS": {
        "name": "Business Registrations",
        "description": (
            "Registrations and licences required for "
            "business establishment and operation."
        ),
    },
    "ENTITY_FORMATION": {
        "name": "Entity Formation",
        "description": (
            "Formation and registration of business entities."
        ),
    },
    "LABOUR_STATUTORY": {
        "name": "Labour & Statutory",
        "description": (
            "Employment, labour and statutory registrations."
        ),
    },
    "INTELLECTUAL_PROPERTY": {
        "name": "Intellectual Property",
        "description": (
            "Trademark and related intellectual-property work."
        ),
    },
    "OTHER_COMPLIANCE": {
        "name": "Other Compliance",
        "description": (
            "Compliance work not covered by a dedicated service."
        ),
    },
}


SERVICES = {
    # =========================================================
    # BUSINESS REGISTRATIONS
    # =========================================================
    "GST_REGISTRATION": {
        "domain": "BUSINESS_REGISTRATIONS",
        "name": "GST Registration",
        "description": "GST registration application and documentation.",
        "fields": (
            (
                "business_constitution",
                "Business Constitution",
                "SELECT",
                True,
                [
                    "Proprietorship",
                    "Partnership",
                    "LLP",
                    "Private Limited",
                    "Public Limited",
                    "Trust / Society",
                    "Other",
                ],
                10,
            ),
            (
                "business_name",
                "Business / Trade Name",
                "TEXT",
                True,
                [],
                20,
            ),
            (
                "principal_business_address",
                "Principal Business Address",
                "LONG_TEXT",
                True,
                [],
                30,
            ),
            (
                "business_activity",
                "Nature of Business Activity",
                "LONG_TEXT",
                True,
                [],
                40,
            ),
            (
                "registration_reason",
                "Reason for GST Registration",
                "TEXT",
                False,
                [],
                50,
            ),
            (
                "additional_places",
                "Additional Places of Business",
                "LONG_TEXT",
                False,
                [],
                60,
            ),
        ),
        "documents": (
            (
                "PAN",
                "PAN",
                "PAN of the applicant/entity as applicable.",
                "IDENTITY_KYC",
                True,
                10,
            ),
            (
                "IDENTITY_PROOF",
                "Promoter / Applicant Identity Proof",
                "Applicable Aadhaar or other identity proof.",
                "IDENTITY_KYC",
                True,
                20,
            ),
            (
                "PHOTOGRAPH",
                "Applicant / Promoter Photograph",
                "Recent photograph where applicable.",
                "IDENTITY_KYC",
                True,
                30,
            ),
            (
                "BUSINESS_CONSTITUTION_PROOF",
                "Business Constitution Proof",
                (
                    "Applicable incorporation, partnership, "
                    "registration or constitution document."
                ),
                "OTHER",
                True,
                40,
            ),
            (
                "BUSINESS_ADDRESS_PROOF",
                "Principal Place of Business Proof",
                "Applicable ownership, rent or address document.",
                "OTHER",
                True,
                50,
            ),
            (
                "BANK_PROOF",
                "Bank Account Proof",
                "Bank account evidence where required.",
                "BANKING",
                False,
                60,
            ),
            (
                "AUTHORIZATION",
                "Authorization / Board Resolution",
                "Authorization where applicable.",
                "OTHER",
                False,
                70,
            ),
        ),
    },

    "UDYAM_REGISTRATION": {
        "domain": "BUSINESS_REGISTRATIONS",
        "name": "MSME (Udyam) Registration",
        "description": "MSME / Udyam registration support.",
        "fields": (
            (
                "enterprise_name",
                "Enterprise Name",
                "TEXT",
                True,
                [],
                10,
            ),
            (
                "business_constitution",
                "Business Constitution",
                "SELECT",
                True,
                [
                    "Proprietorship",
                    "Partnership",
                    "LLP",
                    "Company",
                    "Other",
                ],
                20,
            ),
            (
                "major_activity",
                "Major Activity",
                "SELECT",
                True,
                [
                    "Manufacturing",
                    "Services",
                    "Trading",
                    "Other",
                ],
                30,
            ),
            (
                "business_address",
                "Business Address",
                "LONG_TEXT",
                True,
                [],
                40,
            ),
            (
                "commencement_date",
                "Business Commencement Date",
                "DATE",
                False,
                [],
                50,
            ),
        ),
        "documents": (
            (
                "AADHAAR",
                "Aadhaar",
                "Aadhaar of the relevant applicant.",
                "IDENTITY_KYC",
                True,
                10,
            ),
            (
                "PAN",
                "PAN",
                "PAN of applicant/entity.",
                "IDENTITY_KYC",
                True,
                20,
            ),
            (
                "BUSINESS_DETAILS",
                "Business / Enterprise Details",
                "Available business constitution details.",
                "OTHER",
                True,
                30,
            ),
            (
                "BANK_DETAILS",
                "Bank Details",
                "Business bank account details where applicable.",
                "BANKING",
                False,
                40,
            ),
            (
                "GST_DETAILS",
                "GST Details",
                "GST registration details where applicable.",
                "OTHER",
                False,
                50,
            ),
        ),
    },

    "SHOP_ESTABLISHMENT": {
        "domain": "BUSINESS_REGISTRATIONS",
        "name": "Shop & Establishment Registration",
        "description": "Shop and establishment registration work.",
        "fields": (
            (
                "establishment_name",
                "Establishment Name",
                "TEXT",
                True,
                [],
                10,
            ),
            (
                "establishment_type",
                "Establishment Type",
                "TEXT",
                True,
                [],
                20,
            ),
            (
                "business_address",
                "Establishment Address",
                "LONG_TEXT",
                True,
                [],
                30,
            ),
            (
                "commencement_date",
                "Commencement Date",
                "DATE",
                True,
                [],
                40,
            ),
            (
                "employee_count",
                "Approximate Employee Count",
                "NUMBER",
                False,
                [],
                50,
            ),
        ),
        "documents": (
            (
                "OWNER_IDENTITY",
                "Owner / Promoter Identity Proof",
                "Applicable identity proof.",
                "IDENTITY_KYC",
                True,
                10,
            ),
            (
                "OWNER_PAN",
                "PAN",
                "PAN of the relevant applicant/entity.",
                "IDENTITY_KYC",
                True,
                20,
            ),
            (
                "ADDRESS_PROOF",
                "Establishment Address Proof",
                "Ownership, rent or address proof.",
                "OTHER",
                True,
                30,
            ),
            (
                "BUSINESS_PROOF",
                "Business Constitution Proof",
                "Applicable constitution or registration proof.",
                "OTHER",
                False,
                40,
            ),
            (
                "PHOTOGRAPH",
                "Photograph",
                "Applicant or premises photograph where applicable.",
                "IDENTITY_KYC",
                False,
                50,
            ),
        ),
    },

    "TRADE_LICENSE": {
        "domain": "BUSINESS_REGISTRATIONS",
        "name": "Trade License",
        "description": "Trade licence application and documentation.",
        "fields": (
            (
                "trade_name",
                "Trade / Business Name",
                "TEXT",
                True,
                [],
                10,
            ),
            (
                "business_activity",
                "Business Activity",
                "LONG_TEXT",
                True,
                [],
                20,
            ),
            (
                "premises_address",
                "Business Premises Address",
                "LONG_TEXT",
                True,
                [],
                30,
            ),
            (
                "local_authority",
                "Local Authority / Municipality",
                "TEXT",
                False,
                [],
                40,
            ),
            (
                "license_type",
                "Trade License Type",
                "TEXT",
                False,
                [],
                50,
            ),
        ),
        "documents": (
            (
                "APPLICANT_ID",
                "Applicant Identity Proof",
                "Applicant identity proof.",
                "IDENTITY_KYC",
                True,
                10,
            ),
            (
                "PAN",
                "PAN",
                "PAN of applicant/entity.",
                "IDENTITY_KYC",
                True,
                20,
            ),
            (
                "PREMISES_PROOF",
                "Business Premises Proof",
                "Ownership, rent or occupancy evidence.",
                "OTHER",
                True,
                30,
            ),
            (
                "BUSINESS_PROOF",
                "Business Constitution Proof",
                "Applicable entity/business proof.",
                "OTHER",
                False,
                40,
            ),
            (
                "NOC",
                "NOC / Consent",
                "Applicable NOC or consent document.",
                "OTHER",
                False,
                50,
            ),
        ),
    },

    "IEC_REGISTRATION": {
        "domain": "BUSINESS_REGISTRATIONS",
        "name": "IEC Registration",
        "description": "Import Export Code registration support.",
        "fields": (
            (
                "business_name",
                "Business Name",
                "TEXT",
                True,
                [],
                10,
            ),
            (
                "business_constitution",
                "Business Constitution",
                "SELECT",
                True,
                [
                    "Proprietorship",
                    "Partnership",
                    "LLP",
                    "Company",
                    "Other",
                ],
                20,
            ),
            (
                "business_address",
                "Registered / Business Address",
                "LONG_TEXT",
                True,
                [],
                30,
            ),
            (
                "import_export_activity",
                "Import / Export Activity",
                "SELECT",
                True,
                [
                    "Import",
                    "Export",
                    "Both",
                ],
                40,
            ),
        ),
        "documents": (
            (
                "PAN",
                "PAN",
                "PAN of applicant/entity.",
                "IDENTITY_KYC",
                True,
                10,
            ),
            (
                "IDENTITY_PROOF",
                "Applicant Identity Proof",
                "Applicable identity proof.",
                "IDENTITY_KYC",
                True,
                20,
            ),
            (
                "BUSINESS_ADDRESS_PROOF",
                "Business Address Proof",
                "Applicable address proof.",
                "OTHER",
                True,
                30,
            ),
            (
                "BANK_PROOF",
                "Bank Account Proof",
                "Applicable bank account evidence.",
                "BANKING",
                True,
                40,
            ),
            (
                "CONSTITUTION_PROOF",
                "Business Constitution Proof",
                "Applicable entity constitution proof.",
                "OTHER",
                False,
                50,
            ),
        ),
    },

    # =========================================================
    # ENTITY FORMATION
    # =========================================================
    "PROPRIETORSHIP": {
        "domain": "ENTITY_FORMATION",
        "name": "Proprietorship Setup",
        "description": "Operational setup and registrations for proprietorship.",
        "fields": (
            (
                "proposed_business_name",
                "Proposed Business Name",
                "TEXT",
                True,
                [],
                10,
            ),
            (
                "business_activity",
                "Business Activity",
                "LONG_TEXT",
                True,
                [],
                20,
            ),
            (
                "business_address",
                "Business Address",
                "LONG_TEXT",
                True,
                [],
                30,
            ),
            (
                "required_registrations",
                "Required Registrations",
                "LONG_TEXT",
                False,
                [],
                40,
            ),
        ),
        "documents": (
            (
                "PROPRIETOR_PAN",
                "Proprietor PAN",
                "PAN of proprietor.",
                "IDENTITY_KYC",
                True,
                10,
            ),
            (
                "PROPRIETOR_AADHAAR",
                "Proprietor Aadhaar",
                "Aadhaar of proprietor.",
                "IDENTITY_KYC",
                True,
                20,
            ),
            (
                "PHOTOGRAPH",
                "Proprietor Photograph",
                "Recent photograph.",
                "IDENTITY_KYC",
                False,
                30,
            ),
            (
                "BUSINESS_ADDRESS_PROOF",
                "Business Address Proof",
                "Applicable address proof.",
                "OTHER",
                True,
                40,
            ),
            (
                "BANK_PROOF",
                "Bank Proof",
                "Bank account proof where applicable.",
                "BANKING",
                False,
                50,
            ),
        ),
    },

    "PARTNERSHIP_FIRM": {
        "domain": "ENTITY_FORMATION",
        "name": "Partnership Firm Registration",
        "description": "Partnership firm formation and registration.",
        "fields": (
            (
                "proposed_firm_name",
                "Proposed Firm Name",
                "TEXT",
                True,
                [],
                10,
            ),
            (
                "partner_count",
                "Number of Partners",
                "NUMBER",
                True,
                [],
                20,
            ),
            (
                "business_activity",
                "Business Activity",
                "LONG_TEXT",
                True,
                [],
                30,
            ),
            (
                "registered_address",
                "Registered Address",
                "LONG_TEXT",
                True,
                [],
                40,
            ),
            (
                "capital_contribution",
                "Proposed Capital Contribution",
                "NUMBER",
                False,
                [],
                50,
            ),
        ),
        "documents": (
            (
                "PARTNER_PAN",
                "Partners PAN",
                "PAN documents of all relevant partners.",
                "IDENTITY_KYC",
                True,
                10,
            ),
            (
                "PARTNER_IDENTITY",
                "Partners Identity Proof",
                "Applicable identity proofs.",
                "IDENTITY_KYC",
                True,
                20,
            ),
            (
                "PARTNER_ADDRESS",
                "Partners Address Proof",
                "Applicable address proofs.",
                "IDENTITY_KYC",
                True,
                30,
            ),
            (
                "REGISTERED_OFFICE_PROOF",
                "Registered Office Proof",
                "Ownership/rent/address proof.",
                "OTHER",
                True,
                40,
            ),
            (
                "PARTNERSHIP_DEED_DETAILS",
                "Partnership Deed Information",
                "Proposed deed / partnership terms where available.",
                "OTHER",
                False,
                50,
            ),
        ),
    },

    "LLP_REGISTRATION": {
        "domain": "ENTITY_FORMATION",
        "name": "LLP Registration",
        "description": "Limited Liability Partnership incorporation.",
        "fields": (
            (
                "proposed_name",
                "Proposed LLP Name",
                "TEXT",
                True,
                [],
                10,
            ),
            (
                "partner_count",
                "Number of Partners",
                "NUMBER",
                True,
                [],
                20,
            ),
            (
                "business_activity",
                "Main Business Activity",
                "LONG_TEXT",
                True,
                [],
                30,
            ),
            (
                "registered_office",
                "Registered Office Address",
                "LONG_TEXT",
                True,
                [],
                40,
            ),
            (
                "proposed_contribution",
                "Proposed Contribution",
                "NUMBER",
                False,
                [],
                50,
            ),
        ),
        "documents": (
            (
                "PARTNER_PAN",
                "Partners PAN",
                "PAN of proposed partners.",
                "IDENTITY_KYC",
                True,
                10,
            ),
            (
                "PARTNER_IDENTITY",
                "Partners Identity Proof",
                "Applicable identity proofs.",
                "IDENTITY_KYC",
                True,
                20,
            ),
            (
                "PARTNER_ADDRESS",
                "Partners Address Proof",
                "Applicable address proofs.",
                "IDENTITY_KYC",
                True,
                30,
            ),
            (
                "PHOTOGRAPHS",
                "Partners Photographs",
                "Recent photographs where required.",
                "IDENTITY_KYC",
                False,
                40,
            ),
            (
                "OFFICE_PROOF",
                "Registered Office Proof",
                "Ownership/rent/address proof.",
                "OTHER",
                True,
                50,
            ),
            (
                "NOC",
                "Owner NOC",
                "NOC where applicable.",
                "OTHER",
                False,
                60,
            ),
        ),
    },

    "PRIVATE_LIMITED_COMPANY": {
        "domain": "ENTITY_FORMATION",
        "name": "Private Limited Company Registration",
        "description": "Private Limited Company incorporation.",
        "fields": (
            (
                "proposed_company_name",
                "Proposed Company Name",
                "TEXT",
                True,
                [],
                10,
            ),
            (
                "director_count",
                "Number of Directors",
                "NUMBER",
                True,
                [],
                20,
            ),
            (
                "shareholder_count",
                "Number of Shareholders",
                "NUMBER",
                True,
                [],
                30,
            ),
            (
                "business_activity",
                "Main Business Activity",
                "LONG_TEXT",
                True,
                [],
                40,
            ),
            (
                "registered_office",
                "Registered Office Address",
                "LONG_TEXT",
                True,
                [],
                50,
            ),
            (
                "authorized_capital",
                "Proposed Authorized Capital",
                "NUMBER",
                False,
                [],
                60,
            ),
        ),
        "documents": (
            (
                "DIRECTOR_PAN",
                "Directors PAN",
                "PAN documents of proposed directors.",
                "IDENTITY_KYC",
                True,
                10,
            ),
            (
                "DIRECTOR_IDENTITY",
                "Directors Identity Proof",
                "Applicable identity proofs.",
                "IDENTITY_KYC",
                True,
                20,
            ),
            (
                "DIRECTOR_ADDRESS",
                "Directors Address Proof",
                "Applicable address proofs.",
                "IDENTITY_KYC",
                True,
                30,
            ),
            (
                "DIRECTOR_PHOTOS",
                "Directors Photographs",
                "Recent photographs where required.",
                "IDENTITY_KYC",
                False,
                40,
            ),
            (
                "OFFICE_PROOF",
                "Registered Office Proof",
                "Ownership/rent/address evidence.",
                "OTHER",
                True,
                50,
            ),
            (
                "NOC",
                "Owner NOC",
                "Premises owner NOC where applicable.",
                "OTHER",
                False,
                60,
            ),
            (
                "UTILITY_BILL",
                "Utility Bill",
                "Recent utility bill where applicable.",
                "OTHER",
                False,
                70,
            ),
        ),
    },

    # =========================================================
    # LABOUR & STATUTORY
    # =========================================================
    "PF_REGISTRATION": {
        "domain": "LABOUR_STATUTORY",
        "name": "PF Registration",
        "description": "Employees Provident Fund registration support.",
        "fields": (
            (
                "establishment_name",
                "Establishment Name",
                "TEXT",
                True,
                [],
                10,
            ),
            (
                "employee_count",
                "Employee Count",
                "NUMBER",
                True,
                [],
                20,
            ),
            (
                "commencement_date",
                "Commencement Date",
                "DATE",
                False,
                [],
                30,
            ),
            (
                "business_activity",
                "Business Activity",
                "LONG_TEXT",
                False,
                [],
                40,
            ),
        ),
        "documents": (
            (
                "ENTITY_PAN",
                "Entity PAN",
                "PAN of establishment/entity.",
                "IDENTITY_KYC",
                True,
                10,
            ),
            (
                "ENTITY_PROOF",
                "Entity Constitution Proof",
                "Applicable constitution/registration proof.",
                "OTHER",
                True,
                20,
            ),
            (
                "ADDRESS_PROOF",
                "Establishment Address Proof",
                "Applicable address proof.",
                "OTHER",
                True,
                30,
            ),
            (
                "EMPLOYEE_DETAILS",
                "Employee Details",
                "Employee master/details required for registration.",
                "OTHER",
                True,
                40,
            ),
            (
                "BANK_DETAILS",
                "Bank Details",
                "Establishment bank details where applicable.",
                "BANKING",
                False,
                50,
            ),
        ),
    },

    "ESIC_REGISTRATION": {
        "domain": "LABOUR_STATUTORY",
        "name": "ESIC Registration",
        "description": "Employees State Insurance registration support.",
        "fields": (
            (
                "establishment_name",
                "Establishment Name",
                "TEXT",
                True,
                [],
                10,
            ),
            (
                "employee_count",
                "Employee Count",
                "NUMBER",
                True,
                [],
                20,
            ),
            (
                "commencement_date",
                "Commencement Date",
                "DATE",
                False,
                [],
                30,
            ),
            (
                "business_activity",
                "Business Activity",
                "LONG_TEXT",
                False,
                [],
                40,
            ),
        ),
        "documents": (
            (
                "ENTITY_PAN",
                "Entity PAN",
                "PAN of establishment/entity.",
                "IDENTITY_KYC",
                True,
                10,
            ),
            (
                "ENTITY_PROOF",
                "Entity Constitution Proof",
                "Applicable constitution/registration proof.",
                "OTHER",
                True,
                20,
            ),
            (
                "ADDRESS_PROOF",
                "Establishment Address Proof",
                "Applicable address proof.",
                "OTHER",
                True,
                30,
            ),
            (
                "EMPLOYEE_DETAILS",
                "Employee Details",
                "Employee master/details required for registration.",
                "OTHER",
                True,
                40,
            ),
            (
                "BANK_DETAILS",
                "Bank Details",
                "Establishment bank details where applicable.",
                "BANKING",
                False,
                50,
            ),
        ),
    },

    "PROFESSIONAL_TAX": {
        "domain": "LABOUR_STATUTORY",
        "name": "Professional Tax Registration",
        "description": "Professional Tax registration support.",
        "fields": (
            (
                "applicant_name",
                "Applicant / Entity Name",
                "TEXT",
                True,
                [],
                10,
            ),
            (
                "business_state",
                "Applicable State",
                "TEXT",
                True,
                [],
                20,
            ),
            (
                "employee_count",
                "Employee Count",
                "NUMBER",
                False,
                [],
                30,
            ),
            (
                "business_address",
                "Business Address",
                "LONG_TEXT",
                True,
                [],
                40,
            ),
        ),
        "documents": (
            (
                "PAN",
                "PAN",
                "PAN of applicant/entity.",
                "IDENTITY_KYC",
                True,
                10,
            ),
            (
                "ENTITY_PROOF",
                "Entity / Business Proof",
                "Applicable business proof.",
                "OTHER",
                True,
                20,
            ),
            (
                "ADDRESS_PROOF",
                "Business Address Proof",
                "Applicable address proof.",
                "OTHER",
                True,
                30,
            ),
            (
                "EMPLOYEE_DETAILS",
                "Employee Details",
                "Employee details where applicable.",
                "OTHER",
                False,
                40,
            ),
        ),
    },

    # =========================================================
    # INTELLECTUAL PROPERTY
    # =========================================================
    "TRADEMARK_REGISTRATION": {
        "domain": "INTELLECTUAL_PROPERTY",
        "name": "Trademark Registration",
        "description": "Trademark application preparation and filing.",
        "fields": (
            (
                "applicant_type",
                "Applicant Type",
                "SELECT",
                True,
                [
                    "Individual",
                    "Proprietorship",
                    "Partnership",
                    "LLP",
                    "Company",
                    "Other",
                ],
                10,
            ),
            (
                "trademark_name",
                "Trademark / Brand Name",
                "TEXT",
                True,
                [],
                20,
            ),
            (
                "mark_type",
                "Mark Type",
                "SELECT",
                True,
                [
                    "Word Mark",
                    "Logo / Device",
                    "Combined",
                    "Other",
                ],
                30,
            ),
            (
                "goods_services",
                "Goods / Services Description",
                "LONG_TEXT",
                True,
                [],
                40,
            ),
            (
                "class_details",
                "Trademark Class / Classes",
                "TEXT",
                False,
                [],
                50,
            ),
            (
                "first_use_date",
                "First Use Date",
                "DATE",
                False,
                [],
                60,
            ),
        ),
        "documents": (
            (
                "APPLICANT_PAN",
                "Applicant PAN",
                "PAN of applicant/entity.",
                "IDENTITY_KYC",
                True,
                10,
            ),
            (
                "APPLICANT_ID",
                "Applicant Identity Proof",
                "Identity proof where applicable.",
                "IDENTITY_KYC",
                False,
                20,
            ),
            (
                "ENTITY_PROOF",
                "Business / Entity Proof",
                "Applicable entity constitution proof.",
                "OTHER",
                False,
                30,
            ),
            (
                "LOGO",
                "Logo / Mark Artwork",
                "Logo or artwork where applicable.",
                "OTHER",
                False,
                40,
            ),
            (
                "USER_EVIDENCE",
                "Prior Use Evidence",
                "Evidence of use where applicable.",
                "OTHER",
                False,
                50,
            ),
            (
                "AUTHORIZATION",
                "Authorization",
                "Applicable authorization document.",
                "OTHER",
                False,
                60,
            ),
        ),
    },

    # =========================================================
    # OTHER
    # =========================================================
    "OTHER_COMPLIANCE_WORK": {
        "domain": "OTHER_COMPLIANCE",
        "name": "Other Compliance Work",
        "description": (
            "Compliance work not represented by a dedicated service."
        ),
        "fields": (
            (
                "compliance_type",
                "Compliance Type",
                "TEXT",
                True,
                [],
                10,
            ),
            (
                "authority",
                "Authority / Department",
                "TEXT",
                False,
                [],
                20,
            ),
            (
                "applicable_period",
                "Applicable Period",
                "TEXT",
                False,
                [],
                30,
            ),
            (
                "due_date",
                "Due / Target Date",
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
                "PRIMARY_DOCUMENTS",
                "Primary Supporting Documents",
                "Primary documents required for the compliance.",
                "OTHER",
                True,
                10,
            ),
            (
                "REGISTRATION_DETAILS",
                "Existing Registration Details",
                "Existing licence or registration details where applicable.",
                "OTHER",
                False,
                20,
            ),
            (
                "IDENTITY_ENTITY_PROOF",
                "Identity / Entity Proof",
                "Applicable identity or constitution proof.",
                "IDENTITY_KYC",
                False,
                30,
            ),
            (
                "ADDITIONAL_DOCUMENTS",
                "Additional Supporting Documents",
                "Additional case-specific documents.",
                "OTHER",
                False,
                40,
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

    changed.extend([
        "updated_by",
        "updated_at",
    ])

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
        "Seed the approved Vridhi Compliances operational catalogue."
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
            code="COMPLIANCES",
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
                "VRIDHI_COMPLIANCES_SEED=PASS"
            )
        )

        self.stdout.write(
            f"Domains configured: {len(DOMAINS)}"
        )

        self.stdout.write(
            f"Services configured: {len(SERVICES)}"
        )
