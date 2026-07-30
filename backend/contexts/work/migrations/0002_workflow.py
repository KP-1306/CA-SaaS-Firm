import core.db.uuid7

import contexts.work.models
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ctx_work", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="workitem",
            name="description",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="workitem",
            name="submitted_for_review_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="workitem",
            name="completed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="documentrequest",
            name="description",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="documentrequest",
            name="mandatory",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="documentrequest",
            name="remarks",
            field=models.TextField(blank=True),
        ),
        migrations.CreateModel(
            name="DocumentAttachment",
            fields=[
                ("id", models.UUIDField(default=core.db.uuid7.uuid7, editable=False, primary_key=True, serialize=False)),
                ("tenant_id", models.UUIDField(db_index=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("created_by", models.UUIDField()),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("updated_by", models.UUIDField()),
                ("row_version", models.PositiveIntegerField(default=0)),
                ("document_request_id", models.UUIDField(db_index=True)),
                ("original_name", models.CharField(max_length=255)),
                ("content_type", models.CharField(blank=True, max_length=120)),
                ("size_bytes", models.PositiveIntegerField(default=0)),
                ("file", models.FileField(upload_to=contexts.work.models._attachment_upload_to)),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
    ]
