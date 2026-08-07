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


def _seed():
    call_command(
        "seed_vridhi_loans",
        tenant_id=str(TENANT),
        principal_id=str(PRINCIPAL),
        verbosity=0,
    )


def _loan_domain():
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
def test_complete_vridhi_loan_catalogue_is_created():
    _seed()

    domain = _loan_domain()

    services = {
        row.code: row
        for row in Service.objects.filter(
            tenant_id=TENANT,
            domain_id=domain.id,
            status="ACTIVE",
        )
    }

    assert {
        "HOME_LOAN",
        "CAR_LOAN",
        "MSME_LOAN",
        "OTHER_LOAN",
    }.issubset(set(services))

    assert services["HOME_LOAN"].name == "Home Loan"
    assert services["CAR_LOAN"].name == "Car Loan"
    assert services["MSME_LOAN"].name == "MSME Loan"
    assert services["OTHER_LOAN"].name == "Other Loan"


@pytest.mark.django_db
@pytest.mark.parametrize(
    (
        "service_code",
        "expected_fields",
        "expected_documents",
    ),
    (
        ("HOME_LOAN", 7, 8),
        ("CAR_LOAN", 8, 8),
        ("MSME_LOAN", 8, 9),
        ("OTHER_LOAN", 6, 6),
    ),
)
def test_each_loan_service_has_its_operational_configuration(
    service_code,
    expected_fields,
    expected_documents,
):
    _seed()

    domain = _loan_domain()

    service = Service.objects.get(
        tenant_id=TENANT,
        domain_id=domain.id,
        code=service_code,
    )

    assert ServiceOperationalField.objects.filter(
        tenant_id=TENANT,
        service_id=service.id,
        is_active=True,
    ).count() == expected_fields

    requirement_set = (
        ServiceDocumentRequirementSet.objects.get(
            tenant_id=TENANT,
            service_id=service.id,
            version_number=1,
        )
    )

    assert requirement_set.status == "ACTIVE"

    assert ServiceDocumentRequirement.objects.filter(
        tenant_id=TENANT,
        service_id=service.id,
        requirement_set_id=requirement_set.id,
        is_active=True,
    ).count() == expected_documents


@pytest.mark.django_db
def test_msme_optional_documents_remain_optional():
    _seed()

    domain = _loan_domain()

    service = Service.objects.get(
        tenant_id=TENANT,
        domain_id=domain.id,
        code="MSME_LOAN",
    )

    requirement_set = (
        ServiceDocumentRequirementSet.objects.get(
            tenant_id=TENANT,
            service_id=service.id,
            version_number=1,
        )
    )

    optional_codes = set(
        ServiceDocumentRequirement.objects.filter(
            tenant_id=TENANT,
            requirement_set_id=requirement_set.id,
            mandatory=False,
            is_active=True,
        ).values_list(
            "code",
            flat=True,
        )
    )

    assert optional_codes == {
        "GST_REGISTRATION",
        "UDYAM_REGISTRATION",
        "EXISTING_LOAN_STATEMENTS",
    }


@pytest.mark.django_db
def test_complete_vridhi_loan_seed_is_idempotent():
    _seed()
    _seed()

    domain = _loan_domain()

    services = Service.objects.filter(
        tenant_id=TENANT,
        domain_id=domain.id,
        code__in=[
            "HOME_LOAN",
            "CAR_LOAN",
            "MSME_LOAN",
            "OTHER_LOAN",
        ],
    )

    assert services.count() == 4

    expected = {
        "HOME_LOAN": (7, 8),
        "CAR_LOAN": (8, 8),
        "MSME_LOAN": (8, 9),
        "OTHER_LOAN": (6, 6),
    }

    for code, (field_count, doc_count) in expected.items():
        service = services.get(code=code)

        assert ServiceOperationalField.objects.filter(
            tenant_id=TENANT,
            service_id=service.id,
            is_active=True,
        ).count() == field_count

        sets = ServiceDocumentRequirementSet.objects.filter(
            tenant_id=TENANT,
            service_id=service.id,
            version_number=1,
        )

        assert sets.count() == 1

        requirement_set = sets.get()

        assert ServiceDocumentRequirement.objects.filter(
            tenant_id=TENANT,
            requirement_set_id=requirement_set.id,
            is_active=True,
        ).count() == doc_count
