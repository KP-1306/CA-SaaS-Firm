from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from contexts.configuration.management.commands.seed_vridhi_loans import (
    SERVICES,
    _seed_service,
)
from contexts.configuration.models import Domain, Service


class Command(BaseCommand):
    help = "Install the validated Mudra Loan catalogue configuration only."

    def add_arguments(self, parser):
        parser.add_argument("--tenant-id", required=True)
        parser.add_argument("--principal-id", required=True)

    @transaction.atomic
    def handle(self, *args, **options):
        tenant_id = options["tenant_id"]
        principal_id = options["principal_id"]

        service = (
            Service.objects
            .filter(
                tenant_id=tenant_id,
                code="MUDRA_LOAN",
            )
            .first()
        )

        if service is None:
            raise CommandError(
                "MUDRA_LOAN does not already exist for this tenant. "
                "Refusing to create or modify unrelated loan catalogue data."
            )

        domain = (
            Domain.objects
            .filter(
                tenant_id=tenant_id,
                id=service.domain_id,
            )
            .first()
        )

        if domain is None:
            raise CommandError(
                "Existing MUDRA_LOAN domain could not be resolved."
            )

        _seed_service(
            tenant_id=tenant_id,
            principal_id=principal_id,
            domain=domain,
            code="MUDRA_LOAN",
            definition=SERVICES["MUDRA_LOAN"],
        )

        self.stdout.write(
            self.style.SUCCESS(
                "VRIDHI_MUDRA_SEED=PASS"
            )
        )
