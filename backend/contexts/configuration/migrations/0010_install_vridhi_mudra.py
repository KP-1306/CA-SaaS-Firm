from django.core.management import call_command
from django.db import migrations


def install_vridhi_mudra(apps, schema_editor):
    Service = apps.get_model("ctx_configuration", "Service")

    existing = (
        Service.objects
        .filter(code="MUDRA_LOAN")
        .order_by("created_at", "id")
        .first()
    )

    if existing is None:
        # A fresh database (including Django's test database) may not yet
        # contain the Vridhi loan catalogue. There is nothing to configure.
        return

    tenant_id = existing.tenant_id
    principal_id = (
        existing.updated_by
        or existing.created_by
    )

    if not principal_id:
        raise RuntimeError(
            "Cannot install Vridhi Mudra configuration: "
            "no existing configuration principal was found."
        )

    call_command(
        "seed_vridhi_mudra",
        tenant_id=str(tenant_id),
        principal_id=str(principal_id),
        verbosity=1,
    )


class Migration(migrations.Migration):

    dependencies = [
        ("ctx_configuration", "0009_install_vridhi_compliances"),
    ]

    operations = [
        migrations.RunPython(
            install_vridhi_mudra,
            migrations.RunPython.noop,
        ),
    ]
