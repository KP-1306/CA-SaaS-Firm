
from __future__ import annotations

from uuid import UUID

from django.core.management.base import (
    BaseCommand,
    CommandError,
)
from django.db import transaction

from contexts.configuration.models import (
    CatalogueStatus,
    Vertical,
)


VERTICALS = (
    (
        "ACCOUNTS_TAXATION",
        "Accounts & Taxation",
        "Accounting, direct tax and indirect tax work.",
    ),
    (
        "LOANS",
        "Loans",
        "Loan application, documentation and processing work.",
    ),
    (
        "COMPLIANCES",
        "Compliances",
        "Registrations, statutory filings and compliance work.",
    ),
    (
        "MAP_APPROVAL",
        "Map Approval",
        "Property map preparation and approval work.",
    ),
)


class Command(BaseCommand):
    help = (
        "Create or safely update the four approved Vridhi "
        "operational verticals for one tenant."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--tenant-id",
            required=True,
            help="Tenant UUID for Vridhi Consultants.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        try:
            tenant_id = UUID(options["tenant_id"])
        except (TypeError, ValueError) as exc:
            raise CommandError(
                "tenant-id must be a valid UUID."
            ) from exc

        created_count = 0
        existing_count = 0

        for code, name, description in VERTICALS:
            vertical, created = Vertical.objects.get_or_create(
                tenant_id=tenant_id,
                code=code,
                defaults={
                    "name": name,
                    "description": description,
                    "status": CatalogueStatus.ACTIVE,
                },
            )

            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Created: {vertical.name}"
                    )
                )
                continue

            existing_count += 1

            changed = False

            if vertical.name != name:
                vertical.name = name
                changed = True

            if not vertical.description:
                vertical.description = description
                changed = True

            if vertical.status != CatalogueStatus.ACTIVE:
                vertical.status = CatalogueStatus.ACTIVE
                changed = True

            if changed:
                vertical.save(
                    update_fields=[
                        "name",
                        "description",
                        "status",
                        "updated_at",
                    ]
                )

            self.stdout.write(
                f"Existing: {vertical.name}"
            )

        self.stdout.write(
            self.style.SUCCESS(
                "Vridhi vertical seed completed: "
                f"created={created_count}, "
                f"existing={existing_count}."
            )
        )
