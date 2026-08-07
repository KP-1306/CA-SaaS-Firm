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
        "seed_vridhi_accounts_taxation",
        tenant_id=str(TENANT),
        principal_id=str(PRINCIPAL),
        verbosity=0,
    )


@pytest.mark.django_db
def test_accounts_taxation_catalogue_is_created():
    _seed()

    vertical = Vertical.objects.get(
        tenant_id=TENANT,
        code="ACCOUNTS_TAXATION",
    )

    assert vertical.status == "ACTIVE"

    domains = set(
        Domain.objects.filter(
            tenant_id=TENANT,
            vertical_id=vertical.id,
            status="ACTIVE",
        ).values_list("code", flat=True)
    )

    assert {
        "ACCOUNTING_SERVICES",
        "TAXATION_SERVICES",
    }.issubset(domains)


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("service_code", "field_count", "document_count"),
    (
        ("BOOKKEEPING_ACCOUNTING", 6, 6),
        ("ITR_FILING", 6, 8),
        ("GST_RETURN", 6, 6),
        ("TDS_RETURN", 6, 5),
        ("OTHER_ACCOUNTS_TAXATION", 4, 3),
    ),
)
def test_each_accounts_taxation_service_has_configuration(
    service_code,
    field_count,
    document_count,
):
    _seed()

    service = Service.objects.get(
        tenant_id=TENANT,
        code=service_code,
    )

    assert ServiceOperationalField.objects.filter(
        tenant_id=TENANT,
        service_id=service.id,
        is_active=True,
    ).count() == field_count

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
    ).count() == document_count


@pytest.mark.django_db
def test_accounts_taxation_seed_is_idempotent():
    _seed()
    _seed()

    assert Service.objects.filter(
        tenant_id=TENANT,
        code__in=[
            "BOOKKEEPING_ACCOUNTING",
            "ITR_FILING",
            "GST_RETURN",
            "TDS_RETURN",
            "OTHER_ACCOUNTS_TAXATION",
        ],
    ).count() == 5

    for service in Service.objects.filter(
        tenant_id=TENANT,
        code__in=[
            "BOOKKEEPING_ACCOUNTING",
            "ITR_FILING",
            "GST_RETURN",
            "TDS_RETURN",
            "OTHER_ACCOUNTS_TAXATION",
        ],
    ):
        assert (
            ServiceDocumentRequirementSet.objects.filter(
                tenant_id=TENANT,
                service_id=service.id,
                version_number=1,
            ).count()
            == 1
        )


@pytest.mark.django_db
def test_conditional_documents_are_not_forced_mandatory():
    _seed()

    itr = Service.objects.get(
        tenant_id=TENANT,
        code="ITR_FILING",
    )

    itr_set = ServiceDocumentRequirementSet.objects.get(
        tenant_id=TENANT,
        service_id=itr.id,
        version_number=1,
    )

    optional_itr = set(
        ServiceDocumentRequirement.objects.filter(
            tenant_id=TENANT,
            requirement_set_id=itr_set.id,
            mandatory=False,
        ).values_list("code", flat=True)
    )

    assert {
        "FORM16",
        "DEDUCTION_PROOFS",
        "PREVIOUS_ITR",
    }.issubset(optional_itr)

    gst = Service.objects.get(
        tenant_id=TENANT,
        code="GST_RETURN",
    )

    gst_set = ServiceDocumentRequirementSet.objects.get(
        tenant_id=TENANT,
        service_id=gst.id,
        version_number=1,
    )

    optional_gst = set(
        ServiceDocumentRequirement.objects.filter(
            tenant_id=TENANT,
            requirement_set_id=gst_set.id,
            mandatory=False,
        ).values_list("code", flat=True)
    )

    assert {
        "CREDIT_DEBIT_NOTES",
        "BANK_STATEMENTS",
        "PREVIOUS_GST_RETURN",
    }.issubset(optional_gst)
