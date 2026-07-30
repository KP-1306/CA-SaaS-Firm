from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("ctx_work", "0002_workflow")]
    operations = [
        migrations.AddField(model_name="documentrequest", name="requested_from_contact_id", field=models.UUIDField(blank=True, db_index=True, null=True)),
        migrations.AddField(model_name="documentrequest", name="request_channel", field=models.CharField(choices=[("WHATSAPP", "WhatsApp"), ("EMAIL", "Email"), ("PORTAL", "Portal"), ("PHONE", "Phone"), ("MANUAL", "Manual")], default="WHATSAPP", max_length=12)),
        migrations.AddField(model_name="documentrequest", name="sent_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="documentrequest", name="verified_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="documentrequest", name="verified_by", field=models.UUIDField(blank=True, null=True)),
        migrations.AddField(model_name="documentrequest", name="verification_comment", field=models.TextField(blank=True)),
        migrations.AlterField(model_name="documentrequest", name="status", field=models.CharField(choices=[("REQUESTED", "Requested"), ("PARTIALLY_RECEIVED", "Partially received"), ("RECEIVED", "Received"), ("ACCEPTED", "Accepted"), ("REJECTED", "Rejected"), ("WAIVED", "Waived")], db_index=True, default="REQUESTED", max_length=20)),
        migrations.AlterField(model_name="documentattachment", name="document_request_id", field=models.UUIDField(blank=True, db_index=True, null=True)),
        migrations.AddField(model_name="documentattachment", name="work_item_id", field=models.UUIDField(blank=True, db_index=True, null=True)),
        migrations.AddField(model_name="documentattachment", name="source", field=models.CharField(choices=[("CLIENT", "Client"), ("INTERNAL_TEAM", "Internal team"), ("EMAIL", "Email"), ("WHATSAPP", "WhatsApp"), ("PORTAL", "Portal"), ("PHYSICAL_SCAN", "Physical scan"), ("OTHER", "Other")], default="INTERNAL_TEAM", max_length=20)),
        migrations.AddField(model_name="documentattachment", name="uploaded_by", field=models.UUIDField(blank=True, null=True)),
    ]
