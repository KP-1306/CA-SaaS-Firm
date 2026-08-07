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
    "ACCOUNTING_SERVICES": {
        "name": "Accounting Services",
        "description": "Routine accounting, bookkeeping and books finalisation work.",
    },
    "TAXATION_SERVICES": {
        "name": "Taxation Services",
        "description": "Income tax, GST, TDS and related taxation work.",
    },
}


SERVICES = {
    "BOOKKEEPING_ACCOUNTING": {
        "domain": "ACCOUNTING_SERVICES",
        "name": "Accounting & Bookkeeping",
        "description": "Periodic accounting and bookkeeping services.",
        "fields": (
            ("accounting_period", "Accounting Period", "TEXT", True, [], 10),
            (
                "accounting_frequency",
                "Accounting Frequency",
                "SELECT",
                True,
                ["Monthly", "Quarterly", "Annual", "Other"],
                20,
            ),
            (
                "business_type",
                "Business Type",
                "SELECT",
                True,
                [
                    "Proprietorship",
                    "Partnership",
                    "LLP",
                    "Private Limited",
                    "Other",
                ],
                30,
            ),
            (
                "gst_registered",
                "GST Registered",
                "BOOLEAN",
                False,
                [],
                40,
            ),
            (
                "books_source",
                "Books / Data Source",
                "TEXT",
                False,
                [],
                50,
            ),
            (
                "accounting_notes",
                "Accounting Instructions",
                "LONG_TEXT",
                False,
                [],
                60,
            ),
        ),
        "documents": (
            (
                "BANK_STATEMENTS",
                "Bank Statements",
                "Bank statements for the accounting period.",
                "BANKING",
                True,
                10,
            ),
            (
                "SALES_RECORDS",
                "Sales Invoices / Sales Register",
                "Sales records for the accounting period.",
                "OTHER",
                True,
                20,
            ),
            (
                "PURCHASE_RECORDS",
                "Purchase Invoices / Purchase Register",
                "Purchase and expense records for the accounting period.",
                "OTHER",
                True,
                30,
            ),
            (
                "EXPENSE_RECORDS",
                "Expense Supporting Documents",
                "Available supporting documents for expenses.",
                "OTHER",
                False,
                40,
            ),
            (
                "OPENING_BALANCES",
                "Opening Balances / Previous Trial Balance",
                "Previous closing or opening accounting balances.",
                "OTHER",
                False,
                50,
            ),
            (
                "GST_RECORDS",
                "GST Returns / GST Data",
                "GST records where the client is registered.",
                "OTHER",
                False,
                60,
            ),
        ),
    },

    "ITR_FILING": {
        "domain": "TAXATION_SERVICES",
        "name": "Income Tax Return (ITR)",
        "description": "Income Tax Return preparation and filing.",
        "fields": (
            (
                "assessee_type",
                "Assessee Type",
                "SELECT",
                True,
                [
                    "Individual",
                    "HUF",
                    "Firm",
                    "LLP",
                    "Company",
                    "Other",
                ],
                10,
            ),
            (
                "financial_year",
                "Financial Year",
                "TEXT",
                True,
                [],
                20,
            ),
            (
                "assessment_year",
                "Assessment Year",
                "TEXT",
                True,
                [],
                30,
            ),
            (
                "income_profile",
                "Primary Income Profile",
                "SELECT",
                True,
                [
                    "Salary",
                    "Business / Profession",
                    "Capital Gains",
                    "House Property",
                    "Multiple Sources",
                    "Other",
                ],
                40,
            ),
            (
                "filing_type",
                "Filing Type",
                "SELECT",
                True,
                [
                    "Original",
                    "Revised",
                    "Updated",
                    "Other",
                ],
                50,
            ),
            (
                "itr_notes",
                "Special Filing Notes",
                "LONG_TEXT",
                False,
                [],
                60,
            ),
        ),
        "documents": (
            (
                "PAN_CARD",
                "PAN Card",
                "PAN of the assessee.",
                "IDENTITY_KYC",
                True,
                10,
            ),
            (
                "AADHAAR_CARD",
                "Aadhaar Card",
                "Aadhaar of the assessee where applicable.",
                "IDENTITY_KYC",
                True,
                20,
            ),
            (
                "AIS_TIS",
                "AIS / TIS",
                "Annual Information Statement / Taxpayer Information Summary.",
                "OTHER",
                True,
                30,
            ),
            (
                "FORM16",
                "Form 16",
                "Form 16 where salary income is applicable.",
                "OTHER",
                False,
                40,
            ),
            (
                "BANK_STATEMENTS",
                "Bank Statements",
                "Relevant bank statements for income verification.",
                "BANKING",
                True,
                50,
            ),
            (
                "INCOME_PROOFS",
                "Income Supporting Documents",
                "Applicable documents supporting declared income.",
                "OTHER",
                True,
                60,
            ),
            (
                "DEDUCTION_PROOFS",
                "Deduction / Investment Proofs",
                "Applicable deduction or investment evidence.",
                "OTHER",
                False,
                70,
            ),
            (
                "PREVIOUS_ITR",
                "Previous ITR",
                "Previous return where available.",
                "OTHER",
                False,
                80,
            ),
        ),
    },

    "GST_RETURN": {
        "domain": "TAXATION_SERVICES",
        "name": "GST Return",
        "description": "GST return preparation and filing.",
        "fields": (
            ("gstin", "GSTIN", "TEXT", True, [], 10),
            (
                "filing_period",
                "Filing Period",
                "TEXT",
                True,
                [],
                20,
            ),
            (
                "return_type",
                "Return Type",
                "SELECT",
                True,
                [
                    "GSTR-1",
                    "GSTR-3B",
                    "GSTR-1 & GSTR-3B",
                    "Annual Return",
                    "Other",
                ],
                30,
            ),
            (
                "filing_frequency",
                "Filing Frequency",
                "SELECT",
                True,
                ["Monthly", "Quarterly", "Annual", "Other"],
                40,
            ),
            (
                "period_turnover",
                "Turnover for Filing Period",
                "NUMBER",
                False,
                [],
                50,
            ),
            (
                "gst_notes",
                "GST Filing Notes",
                "LONG_TEXT",
                False,
                [],
                60,
            ),
        ),
        "documents": (
            (
                "GST_REGISTRATION",
                "GST Registration Certificate",
                "GST registration details of the client.",
                "OTHER",
                True,
                10,
            ),
            (
                "SALES_REGISTER",
                "Sales Register / Outward Supply Data",
                "Sales data for the filing period.",
                "OTHER",
                True,
                20,
            ),
            (
                "PURCHASE_REGISTER",
                "Purchase Register / Inward Supply Data",
                "Purchase data for the filing period.",
                "OTHER",
                True,
                30,
            ),
            (
                "CREDIT_DEBIT_NOTES",
                "Credit / Debit Notes",
                "Credit and debit notes for the filing period.",
                "OTHER",
                False,
                40,
            ),
            (
                "BANK_STATEMENTS",
                "Bank Statements",
                "Bank statements where required for reconciliation.",
                "BANKING",
                False,
                50,
            ),
            (
                "PREVIOUS_GST_RETURN",
                "Previous GST Return",
                "Previous return or acknowledgement where required.",
                "OTHER",
                False,
                60,
            ),
        ),
    },

    "TDS_RETURN": {
        "domain": "TAXATION_SERVICES",
        "name": "TDS Return",
        "description": "TDS return preparation and filing.",
        "fields": (
            ("tan", "TAN", "TEXT", True, [], 10),
            ("financial_year", "Financial Year", "TEXT", True, [], 20),
            (
                "quarter",
                "Quarter",
                "SELECT",
                True,
                ["Q1", "Q2", "Q3", "Q4"],
                30,
            ),
            (
                "tds_form",
                "TDS Form",
                "SELECT",
                True,
                ["24Q", "26Q", "27Q", "27EQ", "Other"],
                40,
            ),
            (
                "deductee_count",
                "Approximate Deductee Count",
                "NUMBER",
                False,
                [],
                50,
            ),
            (
                "tds_notes",
                "TDS Filing Notes",
                "LONG_TEXT",
                False,
                [],
                60,
            ),
        ),
        "documents": (
            (
                "TAN_DETAILS",
                "TAN Details",
                "TAN / deductor details.",
                "OTHER",
                True,
                10,
            ),
            (
                "TDS_CHALLANS",
                "TDS Challans",
                "Applicable tax payment challans.",
                "OTHER",
                True,
                20,
            ),
            (
                "DEDUCTEE_DETAILS",
                "Deductee Details",
                "Deductee PAN and transaction details.",
                "OTHER",
                True,
                30,
            ),
            (
                "PAYMENT_SALARY_REGISTER",
                "Payment / Salary Register",
                "Relevant salary or payment register.",
                "OTHER",
                True,
                40,
            ),
            (
                "PREVIOUS_TDS_RETURN",
                "Previous TDS Return",
                "Previous return where available.",
                "OTHER",
                False,
                50,
            ),
        ),
    },

    "OTHER_ACCOUNTS_TAXATION": {
        "domain": "TAXATION_SERVICES",
        "name": "Other Accounts & Taxation",
        "description": "Accounts or taxation work not covered by a dedicated service.",
        "fields": (
            (
                "work_type",
                "Work Type",
                "TEXT",
                True,
                [],
                10,
            ),
            (
                "applicable_period",
                "Applicable Period",
                "TEXT",
                False,
                [],
                20,
            ),
            (
                "work_scope",
                "Scope / Requirement",
                "LONG_TEXT",
                True,
                [],
                30,
            ),
            (
                "statutory_due_date",
                "Statutory / Target Due Date",
                "DATE",
                False,
                [],
                40,
            ),
        ),
        "documents": (
            (
                "PRIMARY_SUPPORTING_DOCUMENTS",
                "Primary Supporting Documents",
                "Primary documents required to perform the work.",
                "OTHER",
                True,
                10,
            ),
            (
                "IDENTITY_TAX_DETAILS",
                "Identity / Tax Registration Details",
                "Applicable PAN, GSTIN, TAN or other registration details.",
                "IDENTITY_KYC",
                False,
                20,
            ),
            (
                "ADDITIONAL_SUPPORT",
                "Additional Supporting Documents",
                "Additional documents relevant to the requested work.",
                "OTHER",
                False,
                30,
            ),
        ),
    },
}


def _update(instance, values, principal_id):
    changed = []

    for name, value in values.items():
        if getattr(instance, name) != value:
            setattr(instance, name, value)
            changed.append(name)

    if not changed:
        return

    instance.updated_by = principal_id
    changed.extend(["updated_by", "updated_at"])
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

    _update(
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

    _update(
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

    obsolete_fields = ServiceOperationalField.objects.filter(
        tenant_id=tenant_id,
        service_id=service.id,
        is_active=True,
    ).exclude(key__in=expected_keys)

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

    _update(
        requirement_set,
        {
            "name": f"{definition['name']} Document Checklist",
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

    obsolete = ServiceDocumentRequirement.objects.filter(
        tenant_id=tenant_id,
        requirement_set_id=requirement_set.id,
        is_active=True,
    ).exclude(code__in=expected_codes)

    for row in obsolete:
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
        "Seed the approved Vridhi Accounts & Taxation "
        "operational catalogue."
    )

    def add_arguments(self, parser):
        parser.add_argument("--tenant-id", required=True)
        parser.add_argument("--principal-id", required=True)

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
            code="ACCOUNTS_TAXATION",
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
                "VRIDHI_ACCOUNTS_TAXATION_SEED=PASS"
            )
        )
        self.stdout.write(
            "Accounts & Taxation -> "
            "Accounting Services / Taxation Services"
        )
        self.stdout.write(
            "Services: Accounting & Bookkeeping, ITR, "
            "GST Return, TDS Return, Other Accounts & Taxation"
        )
