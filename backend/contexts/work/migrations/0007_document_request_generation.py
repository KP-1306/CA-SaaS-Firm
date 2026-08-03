from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        (
            "ctx_work",
            "0006_document_intelligence_foundation",
        ),
    ]

    operations = [
        migrations.AddField(
            model_name="documentrequest",
            name="source_requirement_set_id",
            field=models.UUIDField(
                blank=True,
                db_index=True,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="documentrequest",
            name="source_requirement_id",
            field=models.UUIDField(
                blank=True,
                db_index=True,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="documentrequest",
            name="auto_generated",
            field=models.BooleanField(
                db_index=True,
                default=False,
            ),
        ),
        migrations.AddConstraint(
            model_name="documentrequest",
            constraint=models.UniqueConstraint(
                condition=models.Q(
                    source_requirement_id__isnull=False,
                ),
                fields=(
                    "tenant_id",
                    "work_item_id",
                    "source_requirement_id",
                ),
                name="uq_docreq_work_requirement",
            ),
        ),
        migrations.AddIndex(
            model_name="documentrequest",
            index=models.Index(
                fields=[
                    "tenant_id",
                    "work_item_id",
                    "auto_generated",
                ],
                name="idx_docreq_work_auto",
            ),
        ),
    ]
