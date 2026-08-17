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
    ServiceProcessStep,
    Vertical,
)


TENANT = uuid.UUID(
    "11111111-1111-1111-1111-111111111111"
)

PRINCIPAL = uuid.UUID(
    "22222222-2222-2222-2222-222222222222"
)


SERVICE_COUNTS = {
    "GST_REGISTRATION": (6, 7),
    "UDYAM_REGISTRATION": (5, 5),
    "SHOP_ESTABLISHMENT": (5, 5),
    "TRADE_LICENSE": (5, 5),
    "IEC_REGISTRATION": (4, 5),
    "PROPRIETORSHIP": (4, 5),
    "PARTNERSHIP_FIRM": (5, 5),
    "LLP_REGISTRATION": (5, 6),
    "PRIVATE_LIMITED_COMPANY": (6, 7),
    "PF_REGISTRATION": (4, 5),
    "ESIC_REGISTRATION": (4, 5),
    "PROFESSIONAL_TAX": (4, 4),
    "TRADEMARK_REGISTRATION": (6, 6),
    "OTHER_COMPLIANCE_WORK": (5, 4),
}


def _seed():
    call_command(
        "seed_vridhi_compliances",
        tenant_id=str(TENANT),
        principal_id=str(PRINCIPAL),
        verbosity=0,
    )


@pytest.mark.django_db
def test_compliances_domains_and_services_are_created():
    _seed()

    vertical = Vertical.objects.get(
        tenant_id=TENANT,
        code="COMPLIANCES",
    )

    assert vertical.status == "ACTIVE"

    domain_codes = set(
        Domain.objects.filter(
            tenant_id=TENANT,
            vertical_id=vertical.id,
            status="ACTIVE",
        ).values_list(
            "code",
            flat=True,
        )
    )

    assert {
        "BUSINESS_REGISTRATIONS",
        "ENTITY_FORMATION",
        "LABOUR_STATUTORY",
        "INTELLECTUAL_PROPERTY",
        "OTHER_COMPLIANCE",
    }.issubset(domain_codes)

    service_codes = set(
        Service.objects.filter(
            tenant_id=TENANT,
            code__in=SERVICE_COUNTS.keys(),
            status="ACTIVE",
        ).values_list(
            "code",
            flat=True,
        )
    )

    assert service_codes == set(SERVICE_COUNTS)


@pytest.mark.django_db
@pytest.mark.parametrize(
    (
        "service_code",
        "expected_fields",
        "expected_documents",
    ),
    [
        (code, counts[0], counts[1])
        for code, counts in SERVICE_COUNTS.items()
    ],
)
def test_compliance_service_configuration(
    service_code,
    expected_fields,
    expected_documents,
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
    ).count() == expected_fields

    sets = ServiceDocumentRequirementSet.objects.filter(
        tenant_id=TENANT,
        service_id=service.id,
        version_number=1,
    )

    assert sets.count() == 1

    requirement_set = sets.get()

    assert requirement_set.status == "ACTIVE"

    assert ServiceDocumentRequirement.objects.filter(
        tenant_id=TENANT,
        service_id=service.id,
        requirement_set_id=requirement_set.id,
        is_active=True,
    ).count() == expected_documents


@pytest.mark.django_db
def test_compliances_seed_is_idempotent():
    _seed()
    _seed()

    services = Service.objects.filter(
        tenant_id=TENANT,
        code__in=SERVICE_COUNTS.keys(),
    )

    assert services.count() == len(SERVICE_COUNTS)

    for service in services:
        field_count, document_count = (
            SERVICE_COUNTS[service.code]
        )

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
        ).count() == document_count


@pytest.mark.django_db
def test_conditional_compliance_documents_remain_optional():
    _seed()

    trademark = Service.objects.get(
        tenant_id=TENANT,
        code="TRADEMARK_REGISTRATION",
    )

    requirement_set = (
        ServiceDocumentRequirementSet.objects.get(
            tenant_id=TENANT,
            service_id=trademark.id,
            version_number=1,
        )
    )

    optional = set(
        ServiceDocumentRequirement.objects.filter(
            tenant_id=TENANT,
            requirement_set_id=requirement_set.id,
            mandatory=False,
        ).values_list(
            "code",
            flat=True,
        )
    )

    assert {
        "APPLICANT_ID",
        "ENTITY_PROOF",
        "LOGO",
        "USER_EVIDENCE",
        "AUTHORIZATION",
    }.issubset(optional)


@pytest.mark.django_db
def test_compliance_services_belong_only_to_compliances_vertical():
    _seed()

    vertical = Vertical.objects.get(
        tenant_id=TENANT,
        code="COMPLIANCES",
    )

    domains = Domain.objects.filter(
        tenant_id=TENANT,
        vertical_id=vertical.id,
    )

    domain_ids = set(
        domains.values_list("id", flat=True)
    )

    assert not Service.objects.filter(
        tenant_id=TENANT,
        code__in=SERVICE_COUNTS.keys(),
    ).exclude(
        domain_id__in=domain_ids,
    ).exists()


@pytest.mark.django_db
def test_udyam_process_steps_are_seeded_in_order():
    _seed()

    service = Service.objects.get(
        tenant_id=TENANT,
        code="UDYAM_REGISTRATION",
    )

    rows = list(
        ServiceProcessStep.objects.filter(
            tenant_id=TENANT,
            service_id=service.id,
            is_active=True,
        ).order_by(
            "display_order",
            "name",
            "id",
        )
    )

    assert [
        row.code
        for row in rows
    ] == [
        "CLIENT_INFORMATION",
        "VERIFICATION_PREPARATION",
        "INTERNAL_REVIEW",
        "APPLICATION_REVIEWED",
        "SUBMIT_APPLICATION",
        "APPLICATION_SUBMISSION",
        "QUERY_RESOLUTION",
        "COMPLETION",
    ]

    assert [
        row.display_order
        for row in rows
    ] == [
        10,
        20,
        30,
        40,
        50,
        60,
        70,
        80,
    ]

    assert rows[0].name == "Client Information & Documents"
    assert rows[-1].name == "Registration Completion & Certificate"


@pytest.mark.django_db
def test_udyam_process_seed_is_idempotent():
    _seed()
    _seed()

    service = Service.objects.get(
        tenant_id=TENANT,
        code="UDYAM_REGISTRATION",
    )

    assert ServiceProcessStep.objects.filter(
        tenant_id=TENANT,
        service_id=service.id,
        is_active=True,
    ).count() == 8
