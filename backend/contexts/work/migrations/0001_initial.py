import core.db.uuid7
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='WorkItem',
            fields=[
                ('id', models.UUIDField(default=core.db.uuid7.uuid7, editable=False, primary_key=True, serialize=False)),
                ('tenant_id', models.UUIDField(db_index=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('created_by', models.UUIDField()),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('updated_by', models.UUIDField()),
                ('row_version', models.PositiveIntegerField(default=0)),
                ('title', models.CharField(max_length=200)),
                ('client_id', models.UUIDField(db_index=True)),
                ('service_id', models.UUIDField(blank=True, db_index=True, null=True)),
                ('owner_user_id', models.UUIDField(blank=True, db_index=True, null=True)),
                ('reviewer_user_id', models.UUIDField(blank=True, db_index=True, null=True)),
                ('period', models.CharField(blank=True, max_length=40)),
                ('due_date', models.DateField(blank=True, null=True)),
                ('status', models.CharField(choices=[('NOT_STARTED', 'Not started'), ('IN_PROGRESS', 'In progress'), ('WAITING_FOR_CLIENT', 'Waiting for client'), ('READY_FOR_REVIEW', 'Ready for review'), ('REWORK_REQUIRED', 'Rework required'), ('COMPLETED', 'Completed'), ('CANCELLED', 'Cancelled')], db_index=True, default='NOT_STARTED', max_length=20)),
                ('priority', models.CharField(choices=[('LOW', 'Low'), ('NORMAL', 'Normal'), ('HIGH', 'High'), ('URGENT', 'Urgent')], default='NORMAL', max_length=10)),
                ('review_comment', models.TextField(blank=True)),
                ('notes', models.TextField(blank=True)),
            ],
            options={
                'ordering': ['due_date', '-created_at'],
            },
        ),
        migrations.CreateModel(
            name='WorkNote',
            fields=[
                ('id', models.UUIDField(default=core.db.uuid7.uuid7, editable=False, primary_key=True, serialize=False)),
                ('tenant_id', models.UUIDField(db_index=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('created_by', models.UUIDField()),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('updated_by', models.UUIDField()),
                ('row_version', models.PositiveIntegerField(default=0)),
                ('work_item_id', models.UUIDField(db_index=True)),
                ('author_user_id', models.UUIDField(blank=True, null=True)),
                ('entry', models.TextField()),
                ('from_status', models.CharField(blank=True, max_length=20)),
                ('to_status', models.CharField(blank=True, max_length=20)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='DocumentRequest',
            fields=[
                ('id', models.UUIDField(default=core.db.uuid7.uuid7, editable=False, primary_key=True, serialize=False)),
                ('tenant_id', models.UUIDField(db_index=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('created_by', models.UUIDField()),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('updated_by', models.UUIDField()),
                ('row_version', models.PositiveIntegerField(default=0)),
                ('name', models.CharField(max_length=200)),
                ('client_id', models.UUIDField(db_index=True)),
                ('work_item_id', models.UUIDField(blank=True, db_index=True, null=True)),
                ('requested_date', models.DateField(blank=True, null=True)),
                ('due_date', models.DateField(blank=True, null=True)),
                ('received_date', models.DateField(blank=True, null=True)),
                ('status', models.CharField(choices=[('REQUESTED', 'Requested'), ('PARTIALLY_RECEIVED', 'Partially received'), ('RECEIVED', 'Received'), ('NOT_APPLICABLE', 'Not applicable')], db_index=True, default='REQUESTED', max_length=20)),
                ('client_visible', models.BooleanField(default=True)),
                ('notes', models.TextField(blank=True)),
            ],
            options={
                'ordering': ['due_date', '-created_at'],
            },
        ),
    ]
