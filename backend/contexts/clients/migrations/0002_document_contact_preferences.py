from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("ctx_clients", "0001_initial")]
    operations = [
        migrations.AddField(model_name="clientcontact", name="whatsapp_number", field=models.CharField(blank=True, max_length=20)),
        migrations.AddField(model_name="clientcontact", name="preferred_channel", field=models.CharField(choices=[("WHATSAPP", "WhatsApp"), ("EMAIL", "Email"), ("PHONE", "Phone"), ("PORTAL", "Portal"), ("MANUAL", "Manual")], default="WHATSAPP", max_length=12)),
        migrations.AddField(model_name="clientcontact", name="can_receive_document_requests", field=models.BooleanField(default=True)),
    ]
