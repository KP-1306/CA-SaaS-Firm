import os

from django.core.management import call_command
from django.db import migrations


def install_vridhi_compliances(apps, schema_editor):
    Vertical = apps.get_model("ctx_configuration", "Vertical")
    Service = apps.get_model("ctx_configuration", "Service")

    tenant_id = os.environ.get("VRIDHI_PROVIDER_TENANT_ID")

    existing = None

    if tenant_id:
        existing = (
            Vertical.objects
            .filter(tenant_id=tenant_id)
            .order_by("created_at", "id")
            .first()
        )

    if existing is None:
        existing = (
            Vertical.objects
            .filter(code="COMPLIANCES")
            .order_by("created_at", "id")
            .first()
        )

    if existing is None:
        existing_service = (
            Service.objects
            .order_by("created_at", "id")
            .first()
        )

        if existing_service is None:
            raise RuntimeError(
                "Cannot install Vridhi compliances: "
                "no existing tenant configuration was found."
            )

        tenant_id = existing_service.tenant_id
        principal_id = (
            existing_service.updated_by
            or existing_service.created_by
        )
    else:
        tenant_id = existing.tenant_id
        principal_id = (
            existing.updated_by
            or existing.created_by
        )

    if not principal_id:
        raise RuntimeError(
            "Cannot install Vridhi compliances: "
            "no existing configuration principal was found."
        )

    call_command(
        "seed_vridhi_compliances",
        tenant_id=str(tenant_id),
        principal_id=str(principal_id),
        verbosity=1,
    )


class Migration(migrations.Migration):

    dependencies = [
        ("ctx_configuration", "0008_service_process_step"),
    ]

    operations = [
        migrations.RunPython(
            install_vridhi_compliances,
            migrations.RunPython.noop,
        ),
    ]
