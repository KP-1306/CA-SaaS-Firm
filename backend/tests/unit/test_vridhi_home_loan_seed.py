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


@pytest.mark.django_db
def test_vridhi_home_loan_seed_creates_business_configuration():
    call_command(
        "seed_vridhi_home_loan",
        tenant_id=str(TENANT),
        principal_id=str(PRINCIPAL),
        verbosity=0,
    )

    loans = Vertical.objects.get(
        tenant_id=TENANT,
        code="LOANS",
    )

    assert loans.name == "Loans"
    assert loans.status == "ACTIVE"

    domain = Domain.objects.get(
        tenant_id=TENANT,
        vertical_id=loans.id,
        code="LOAN_SERVICES",
    )

    assert domain.name == "Loan Services"
    assert domain.status == "ACTIVE"

    service = Service.objects.get(
        tenant_id=TENANT,
        domain_id=domain.id,
        code="HOME_LOAN",
    )

    assert service.name == "Home Loan"
    assert service.status == "ACTIVE"

    fields = ServiceOperationalField.objects.filter(
        tenant_id=TENANT,
        service_id=service.id,
    )

    assert fields.count() == 7

    keys = set(
        fields.values_list(
            "key",
            flat=True,
        )
    )

    assert keys == {
        "requested_loan_amount",
        "applicant_type",
        "employment_type",
        "property_type",
        "property_location",
        "preferred_lender",
        "existing_monthly_emi",
    }

    requirement_set = (
        ServiceDocumentRequirementSet.objects.get(
            tenant_id=TENANT,
            service_id=service.id,
            version_number=1,
        )
    )

    assert requirement_set.status == "ACTIVE"

    requirements = (
        ServiceDocumentRequirement.objects.filter(
            tenant_id=TENANT,
            service_id=service.id,
            requirement_set_id=requirement_set.id,
            is_active=True,
        )
    )

    assert requirements.count() == 8

    codes = set(
        requirements.values_list(
            "code",
            flat=True,
        )
    )

    assert codes == {
        "PAN_CARD",
        "AADHAAR_CARD",
        "PHOTOGRAPH",
        "BANK_STATEMENTS",
        "INCOME_PROOF",
        "ADDRESS_PROOF",
        "PROPERTY_DOCUMENTS",
        "EMPLOYMENT_BUSINESS_PROOF",
    }

    assert requirements.filter(
        mandatory=True,
    ).count() == 8


@pytest.mark.django_db
def test_vridhi_home_loan_seed_is_idempotent():
    call_command(
        "seed_vridhi_home_loan",
        tenant_id=str(TENANT),
        principal_id=str(PRINCIPAL),
        verbosity=0,
    )

    call_command(
        "seed_vridhi_home_loan",
        tenant_id=str(TENANT),
        principal_id=str(PRINCIPAL),
        verbosity=0,
    )

    loans = Vertical.objects.get(
        tenant_id=TENANT,
        code="LOANS",
    )

    domain = Domain.objects.get(
        tenant_id=TENANT,
        vertical_id=loans.id,
        code="LOAN_SERVICES",
    )

    service = Service.objects.get(
        tenant_id=TENANT,
        domain_id=domain.id,
        code="HOME_LOAN",
    )

    assert Vertical.objects.filter(
        tenant_id=TENANT,
        code="LOANS",
    ).count() == 1

    assert Domain.objects.filter(
        tenant_id=TENANT,
        vertical_id=loans.id,
        code="LOAN_SERVICES",
    ).count() == 1

    assert Service.objects.filter(
        tenant_id=TENANT,
        domain_id=domain.id,
        code="HOME_LOAN",
    ).count() == 1

    assert ServiceOperationalField.objects.filter(
        tenant_id=TENANT,
        service_id=service.id,
    ).count() == 7

    requirement_sets = (
        ServiceDocumentRequirementSet.objects.filter(
            tenant_id=TENANT,
            service_id=service.id,
            version_number=1,
        )
    )

    assert requirement_sets.count() == 1

    requirement_set = requirement_sets.get()

    assert ServiceDocumentRequirement.objects.filter(
        tenant_id=TENANT,
        requirement_set_id=requirement_set.id,
    ).count() == 8
