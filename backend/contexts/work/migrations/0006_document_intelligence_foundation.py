from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("ctx_work", "0005_workitem_estimated_hours"),
    ]

    operations = [
        migrations.AddField(
            model_name="documentrequest",
            name="category",
            field=models.CharField(
                choices=[
                    ("GST", "GST"),
                    ("TDS", "TDS"),
                    ("INCOME_TAX", "Income Tax"),
                    ("ROC_MCA", "ROC / MCA"),
                    ("AUDIT", "Audit"),
                    ("ACCOUNTING", "Accounting"),
                    ("PAYROLL", "Payroll"),
                    ("BANKING", "Banking"),
                    ("REGISTRATION", "Registration"),
                    ("IDENTITY_KYC", "Identity / KYC"),
                    ("LEGAL", "Legal"),
                    ("OTHER", "Other"),
                ],
                db_index=True,
                default="OTHER",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="documentrequest",
            name="financial_year",
            field=models.CharField(
                blank=True,
                db_index=True,
                help_text="Financial year, for example 2025-26.",
                max_length=9,
            ),
        ),
        migrations.AddField(
            model_name="documentrequest",
            name="assessment_year",
            field=models.CharField(
                blank=True,
                db_index=True,
                help_text="Assessment year, for example 2026-27.",
                max_length=9,
            ),
        ),
        migrations.AddField(
            model_name="documentrequest",
            name="filing_period",
            field=models.CharField(
                blank=True,
                db_index=True,
                help_text="Month, quarter or statutory filing period.",
                max_length=30,
            ),
        ),
        migrations.AddField(
            model_name="documentrequest",
            name="valid_from",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="documentrequest",
            name="expires_on",
            field=models.DateField(
                blank=True,
                db_index=True,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="documentattachment",
            name="sha256",
            field=models.CharField(
                blank=True,
                db_index=True,
                max_length=64,
            ),
        ),
        migrations.AddField(
            model_name="documentattachment",
            name="version_number",
            field=models.PositiveIntegerField(default=1),
        ),
        migrations.AddField(
            model_name="documentattachment",
            name="version_label",
            field=models.CharField(blank=True, max_length=30),
        ),
        migrations.AddField(
            model_name="documentattachment",
            name="supersedes_attachment_id",
            field=models.UUIDField(
                blank=True,
                db_index=True,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="documentattachment",
            name="duplicate_of_attachment_id",
            field=models.UUIDField(
                blank=True,
                db_index=True,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="documentattachment",
            name="is_duplicate",
            field=models.BooleanField(
                db_index=True,
                default=False,
            ),
        ),
        migrations.AddIndex(
            model_name="documentattachment",
            index=models.Index(
                fields=[
                    "tenant_id",
                    "document_request_id",
                    "version_number",
                ],
                name="idx_docatt_req_version",
            ),
        ),
        migrations.AddIndex(
            model_name="documentattachment",
            index=models.Index(
                fields=["tenant_id", "sha256"],
                name="idx_docatt_tenant_hash",
            ),
        ),
    ]
