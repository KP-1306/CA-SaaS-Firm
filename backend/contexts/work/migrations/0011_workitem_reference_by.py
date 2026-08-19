from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ctx_work', '0010_work_process_state'),
    ]

    operations = [
        migrations.AddField(
            model_name='workitem',
            name='reference_by',
            field=models.CharField(blank=True, default='', max_length=200),
        ),
    ]
