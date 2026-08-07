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


SERVICE_COUNTS = {
    "RESIDENTIAL_MAP_APPROVAL": (8, 7),
    "COMMERCIAL_MAP_APPROVAL": (8, 8),
    "LAYOUT_APPROVAL": (7, 6),
    "COMPLETION_CERTIFICATE": (6, 7),
    "BUILDING_REGULARIZATION": (8, 8),
    "OTHER_MAP_APPROVAL_WORK": (5, 5),
}


def _seed():
    call_command(
        "seed_vridhi_map_approval",
        tenant_id=str(TENANT),
        principal_id=str(PRINCIPAL),
        verbosity=0,
    )


@pytest.mark.django_db
def test_map_approval_domains_and_services_are_created():
    _seed()

    vertical = Vertical.objects.get(
        tenant_id=TENANT,
        code="MAP_APPROVAL",
    )

    assert vertical.status == "ACTIVE"

    domains = set(
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
        "BUILDING_MAP_APPROVALS",
        "COMPLETION_REGULARIZATION",
    }.issubset(domains)

    services = set(
        Service.objects.filter(
            tenant_id=TENANT,
            code__in=SERVICE_COUNTS.keys(),
            status="ACTIVE",
        ).values_list(
            "code",
            flat=True,
        )
    )

    assert services == set(SERVICE_COUNTS)


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
def test_each_map_service_has_configuration(
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
def test_map_approval_seed_is_idempotent():
    _seed()
    _seed()

    services = Service.objects.filter(
        tenant_id=TENANT,
        code__in=SERVICE_COUNTS.keys(),
    )

    assert services.count() == len(SERVICE_COUNTS)

    for service in services:
        expected_fields, expected_documents = (
            SERVICE_COUNTS[service.code]
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

        assert ServiceDocumentRequirement.objects.filter(
            tenant_id=TENANT,
            requirement_set_id=requirement_set.id,
            is_active=True,
        ).count() == expected_documents


@pytest.mark.django_db
def test_map_services_belong_only_to_map_approval_vertical():
    _seed()

    vertical = Vertical.objects.get(
        tenant_id=TENANT,
        code="MAP_APPROVAL",
    )

    domain_ids = set(
        Domain.objects.filter(
            tenant_id=TENANT,
            vertical_id=vertical.id,
        ).values_list(
            "id",
            flat=True,
        )
    )

    assert not Service.objects.filter(
        tenant_id=TENANT,
        code__in=SERVICE_COUNTS.keys(),
    ).exclude(
        domain_id__in=domain_ids,
    ).exists()


@pytest.mark.django_db
def test_case_specific_map_documents_remain_optional():
    _seed()

    service = Service.objects.get(
        tenant_id=TENANT,
        code="BUILDING_REGULARIZATION",
    )

    requirement_set = (
        ServiceDocumentRequirementSet.objects.get(
            tenant_id=TENANT,
            service_id=service.id,
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
        "EXISTING_MAP",
        "LOCAL_PROPERTY_RECORD",
        "NOTICE_ORDER",
        "NOC_SUPPORTING",
    }.issubset(optional)
