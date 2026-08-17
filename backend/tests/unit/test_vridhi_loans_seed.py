from __future__ import annotations

import uuid

import pytest
from django.core.management import call_command

from contexts.configuration.models import (
    Domain,
    Service,
    ServiceDocumentRequirement,
    ServiceDocumentRequirementSet,
    ServiceOperationalField,
    Vertical,
)


TENANT = uuid.UUID(
    "11111111-1111-1111-1111-111111111111"
)

PRINCIPAL = uuid.UUID(
    "22222222-2222-2222-2222-222222222222"
)


EXPECTED = {
    "MSY_LOAN": ("M.S.Y. Loan", 17),
    "BRE_LOAN": ("B.R.E. Loan", 10),
    "MUDRA_LOAN": ("Mudra Loan", 14),
    "CAR_LOAN": ("Car Loan", 7),
    "HOME_LOAN": ("Home Loan", 7),
    "LAP_LOAN": ("Loan Against Property (LAP)", 7),
    "MSME_LOAN": ("MSME Loan", 7),
    "LOAN_TAKE_OVER": ("Loan Take Over", 7),
    "OD_LIMIT": ("OD (Overdraft) Limit", 8),
    "COMMERCIAL_LOAN": ("Commercial Loan", 8),
}


def _seed():
    call_command(
        "seed_vridhi_loans",
        tenant_id=str(TENANT),
        principal_id=str(PRINCIPAL),
        verbosity=0,
    )


def _domain():
    loans = Vertical.objects.get(
        tenant_id=TENANT,
        code="LOANS",
    )

    return Domain.objects.get(
        tenant_id=TENANT,
        vertical_id=loans.id,
        code="LOAN_SERVICES",
    )


@pytest.mark.django_db
def test_exact_company_approved_loan_catalogue():
    _seed()

    domain = _domain()

    observed = {
        row.code: row.name
        for row in Service.objects.filter(
            tenant_id=TENANT,
            domain_id=domain.id,
            status="ACTIVE",
        )
    }

    expected = {
        code: name
        for code, (name, _count)
        in EXPECTED.items()
    }

    assert observed == expected


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("service_code", "document_count"),
    [
        (code, count)
        for code, (_name, count)
        in EXPECTED.items()
    ],
)
def test_company_document_requirements(
    service_code,
    document_count,
):
    _seed()

    domain = _domain()

    service = Service.objects.get(
        tenant_id=TENANT,
        domain_id=domain.id,
        code=service_code,
    )

    requirement_set = (
        ServiceDocumentRequirementSet.objects.get(
            tenant_id=TENANT,
            service_id=service.id,
            version_number=1,
        )
    )

    assert requirement_set.status == "ACTIVE"

    assert (
        ServiceDocumentRequirement.objects.filter(
            tenant_id=TENANT,
            service_id=service.id,
            requirement_set_id=requirement_set.id,
            is_active=True,
        ).count()
        == document_count
    )


@pytest.mark.django_db
def test_company_conditional_requirements_are_optional():
    _seed()

    domain = _domain()

    expected_optional = {
        "MSY_LOAN": {
            "BS79_RENTED_SHOP",
            "OWNER_ELECTRICITY_BILL",
            "RENT_AGREEMENT",
            "CC_STOCK_STATEMENT",
        },
        "BRE_LOAN": {
            "RENT_AGREEMENT_ELECTRICITY",
        },
        "CAR_LOAN": {
            "SALARY_SLIPS_3_MONTHS",
        },
        "HOME_LOAN": {
            "SALARY_SLIPS_3_MONTHS",
            "UDYAM_GST_BUSINESS",
        },
        "LAP_LOAN": {
            "CERTIFICATE_143",
        },
    }

    for service_code, expected_codes in expected_optional.items():

        service = Service.objects.get(
            tenant_id=TENANT,
            domain_id=domain.id,
            code=service_code,
        )

        observed = set(
            ServiceDocumentRequirement.objects.filter(
                tenant_id=TENANT,
                service_id=service.id,
                is_active=True,
                mandatory=False,
            ).values_list(
                "code",
                flat=True,
            )
        )

        assert observed == expected_codes


@pytest.mark.django_db
def test_existing_operational_configuration_is_preserved():
    _seed()

    domain = _domain()

    expected_fields = {
        "HOME_LOAN": 7,
        "CAR_LOAN": 8,
        "MSME_LOAN": 8,
    }

    for code, count in expected_fields.items():

        service = Service.objects.get(
            tenant_id=TENANT,
            domain_id=domain.id,
            code=code,
        )

        assert (
            ServiceOperationalField.objects.filter(
                tenant_id=TENANT,
                service_id=service.id,
                is_active=True,
            ).count()
            == count
        )


@pytest.mark.django_db
def test_unprovided_operational_fields_are_not_invented():
    _seed()

    domain = _domain()

    codes = {
        "MSY_LOAN",
        "BRE_LOAN",
        "LAP_LOAN",
        "LOAN_TAKE_OVER",
        "OD_LIMIT",
        "COMMERCIAL_LOAN",
    }

    services = Service.objects.filter(
        tenant_id=TENANT,
        domain_id=domain.id,
        code__in=codes,
    )

    assert services.count() == len(codes)

    for service in services:

        assert not (
            ServiceOperationalField.objects.filter(
                tenant_id=TENANT,
                service_id=service.id,
                is_active=True,
            ).exists()
        )


@pytest.mark.django_db
def test_obsolete_generic_other_loan_is_inactive():
    _seed()

    domain = _domain()

    assert not Service.objects.filter(
        tenant_id=TENANT,
        domain_id=domain.id,
        code="OTHER_LOAN",
        status="ACTIVE",
    ).exists()


@pytest.mark.django_db
def test_company_seed_is_idempotent():
    _seed()
    _seed()

    domain = _domain()

    active = Service.objects.filter(
        tenant_id=TENANT,
        domain_id=domain.id,
        status="ACTIVE",
    )

    assert active.count() == 10

    assert set(
        active.values_list(
            "code",
            flat=True,
        )
    ) == set(EXPECTED)

    for service in active:

        sets = (
            ServiceDocumentRequirementSet.objects.filter(
                tenant_id=TENANT,
                service_id=service.id,
                version_number=1,
            )
        )

        assert sets.count() == 1
