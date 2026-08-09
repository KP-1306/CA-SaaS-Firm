from __future__ import annotations

import datetime as dt

from django.core.management.base import (
    BaseCommand,
    CommandError,
)
from django.db import transaction

from contexts.configuration.models import (
    ComplianceDeadlineRule,
    Service,
)


# Business-facing aliases retained by Vridhi.
#
# Income-tax Rules, 2026 equivalents:
#   24Q -> Form 138
#   26Q -> Form 140
#   27Q -> Form 144
#
# 27EQ is deliberately excluded because it is TCS.
TDS_FORMS = (
    "24Q",
    "26Q",
    "27Q",
)


# Indian financial-year quarterly TDS statement deadlines.
#
# period_start_month = 4 means Apr-Mar:
#
#   Q1 Apr-Jun -> 31 Jul
#   Q2 Jul-Sep -> 31 Oct
#   Q3 Oct-Dec -> 31 Jan
#   Q4 Jan-Mar -> 31 May
DEADLINES = (
    # period_number, due_month_offset, due_day
    (1, 1, 31),
    (2, 1, 31),
    (3, 1, 31),
    (4, 2, 31),
)


EFFECTIVE_FROM = dt.date(
    2026,
    4,
    1,
)


class Command(BaseCommand):
    help = (
        "Seed Income-tax Rules 2026 quarterly TDS "
        "deadline rules for an existing service."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--tenant-id",
            required=True,
        )
        parser.add_argument(
            "--principal-id",
            required=True,
        )
        parser.add_argument(
            "--service-code",
            required=True,
        )

    @transaction.atomic
    def handle(self, *args, **options):
        tenant_id = options["tenant_id"]
        principal_id = options["principal_id"]
        service_code = options["service_code"]

        services = Service.objects.filter(
            tenant_id=tenant_id,
            code=service_code,
        )

        count = services.count()

        if count != 1:
            raise CommandError(
                "Expected exactly one existing service "
                f"for code {service_code!r}; found {count}. "
                "No deadline rules were changed."
            )

        service = services.get()

        created_count = 0
        updated_count = 0

        for form in TDS_FORMS:
            for (
                period_number,
                due_month_offset,
                due_day,
            ) in DEADLINES:
                rule, created = (
                    ComplianceDeadlineRule.objects.update_or_create(
                        tenant_id=tenant_id,
                        service_id=service.id,
                        frequency="QUARTERLY",
                        period_start_month=4,
                        period_number=period_number,
                        applicability={
                            "tds_form": form,
                        },
                        effective_from=EFFECTIVE_FROM,
                        defaults={
                            "updated_by": principal_id,
                            "due_day": due_day,
                            "due_month_offset": (
                                due_month_offset
                            ),
                            "effective_until": None,
                            "is_active": True,
                        },
                        create_defaults={
                            "created_by": principal_id,
                            "updated_by": principal_id,
                            "due_day": due_day,
                            "due_month_offset": (
                                due_month_offset
                            ),
                            "effective_until": None,
                            "is_active": True,
                        },
                    )
                )

                if created:
                    created_count += 1
                else:
                    updated_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                "TDS_DEADLINES_2026_SEED=PASS"
            )
        )

        self.stdout.write(
            f"Service: {service.code} ({service.id})"
        )

        self.stdout.write(
            f"Rules created: {created_count}"
        )

        self.stdout.write(
            f"Rules updated: {updated_count}"
        )

        self.stdout.write(
            "Forms: 24Q, 26Q, 27Q"
        )

        self.stdout.write(
            "Effective from: 2026-04-01"
        )
