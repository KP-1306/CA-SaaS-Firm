# Employee Operations V1 — employee foundation + skill catalogue (additive).

import core.db.uuid7
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ctx_identity", "0003_employee_expertise"),
    ]

    operations = [
        migrations.AddField(
            model_name="employee",
            name="department_id",
            field=models.UUIDField(blank=True, db_index=True, null=True),
        ),
        migrations.AddField(
            model_name="employee",
            name="designation_id",
            field=models.UUIDField(blank=True, db_index=True, null=True),
        ),
        migrations.AddField(
            model_name="employee",
            name="manager_id",
            field=models.UUIDField(blank=True, db_index=True, null=True),
        ),
        migrations.AddField(
            model_name="employee",
            name="employment_type",
            field=models.CharField(
                blank=True,
                choices=[
                    ("FULL_TIME", "Full time"),
                    ("PART_TIME", "Part time"),
                    ("ARTICLE", "Article assistant"),
                    ("INTERN", "Intern"),
                    ("CONTRACT", "Contract"),
                    ("CONSULTANT", "Consultant"),
                ],
                max_length=15,
            ),
        ),
        migrations.AddField(
            model_name="employee",
            name="employment_status",
            field=models.CharField(
                blank=True,
                choices=[
                    ("PROBATION", "Probation"),
                    ("CONFIRMED", "Confirmed"),
                    ("NOTICE_PERIOD", "Notice period"),
                    ("EXITED", "Exited"),
                    ("SUSPENDED", "Suspended"),
                ],
                max_length=15,
            ),
        ),
        migrations.AddField(
            model_name="employee",
            name="joining_date",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="employee",
            name="confirmation_date",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="employee",
            name="exit_date",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="employee",
            name="timezone",
            field=models.CharField(blank=True, max_length=64),
        ),
        migrations.AddField(
            model_name="employee",
            name="notes",
            field=models.TextField(blank=True),
        ),
        migrations.AddConstraint(
            model_name="employee",
            constraint=models.UniqueConstraint(
                fields=("tenant_id", "employee_code"),
                condition=models.Q(("employee_code", ""), _negated=True),
                name="uq_employee_code_tenant",
            ),
        ),
        migrations.CreateModel(
            name="SkillCatalogue",
            fields=[
                ("id", models.UUIDField(default=core.db.uuid7.uuid7, editable=False, primary_key=True, serialize=False)),
                ("tenant_id", models.UUIDField(db_index=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("created_by", models.UUIDField()),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("updated_by", models.UUIDField()),
                ("row_version", models.PositiveIntegerField(default=0)),
                ("name", models.CharField(max_length=160)),
                ("code", models.CharField(max_length=40)),
                ("category_key", models.CharField(blank=True, max_length=40)),
                ("description", models.TextField(blank=True)),
                ("is_custom", models.BooleanField(default=False)),
                ("is_active", models.BooleanField(default=True)),
            ],
            options={"ordering": ["name"]},
        ),
        migrations.AddConstraint(
            model_name="skillcatalogue",
            constraint=models.UniqueConstraint(fields=("tenant_id", "code"), name="uq_skill_code_tenant"),
        ),
    ]
