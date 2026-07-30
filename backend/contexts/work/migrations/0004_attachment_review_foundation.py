from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("ctx_work", "0003_document_operations")]
    operations = [
        migrations.AddField(
            model_name="documentattachment",
            name="review_status",
            field=models.CharField(
                choices=[
                    ("PENDING_REVIEW", "Pending review"),
                    ("ACCEPTED", "Accepted"),
                    ("REJECTED", "Rejected"),
                    ("SUPERSEDED", "Superseded"),
                ],
                db_index=True,
                default="PENDING_REVIEW",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="documentattachment",
            name="reviewed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="documentattachment",
            name="reviewed_by",
            field=models.UUIDField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="documentattachment",
            name="review_comment",
            field=models.TextField(blank=True),
        ),
    ]
