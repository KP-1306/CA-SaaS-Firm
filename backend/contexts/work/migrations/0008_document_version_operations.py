from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        (
            "ctx_work",
            "0007_document_request_generation",
        ),
    ]

    operations = [
        migrations.AddField(
            model_name="documentattachment",
            name="duplicate_resolution",
            field=models.CharField(
                choices=[
                    (
                        "NOT_APPLICABLE",
                        "Not applicable",
                    ),
                    (
                        "UNRESOLVED",
                        "Unresolved",
                    ),
                    (
                        "CONFIRMED_DUPLICATE",
                        "Confirmed duplicate",
                    ),
                    (
                        "KEPT_AS_VERSION",
                        "Kept as version",
                    ),
                ],
                db_index=True,
                default="NOT_APPLICABLE",
                max_length=22,
            ),
        ),
        migrations.AddField(
            model_name="documentattachment",
            name="is_canonical",
            field=models.BooleanField(
                db_index=True,
                default=False,
                help_text=(
                    "The accepted attachment selected as the "
                    "current authoritative document."
                ),
            ),
        ),
        migrations.AddIndex(
            model_name="documentattachment",
            index=models.Index(
                fields=[
                    "tenant_id",
                    "document_request_id",
                    "is_canonical",
                ],
                name="idx_docatt_req_canonical",
            ),
        ),
        migrations.AddIndex(
            model_name="documentattachment",
            index=models.Index(
                fields=[
                    "tenant_id",
                    "is_duplicate",
                    "duplicate_resolution",
                ],
                name="idx_docatt_dup_resolution",
            ),
        ),
    ]
