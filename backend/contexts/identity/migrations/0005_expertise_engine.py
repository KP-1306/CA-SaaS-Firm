# Employee Operations V1 — expertise engine extension + reversible proficiency
# remap (additive; no expertise rows destroyed; legacy JSON untouched).

from django.db import migrations, models


# Approved reversible mapping (decision 13).
_FORWARD = {"BASIC": "BEGINNER", "EXPERT": "SME"}
_REVERSE = {"BEGINNER": "BASIC", "SME": "EXPERT"}


def remap_forward(apps, schema_editor):
    """BASIC -> BEGINNER, EXPERT -> SME. INTERMEDIATE/ADVANCED unchanged.

    Idempotent: values already in the target vocabulary are left as-is.
    REVIEWER is a new level and is never produced by this data migration.
    """
    EmployeeExpertise = apps.get_model("ctx_identity", "EmployeeExpertise")
    for old, new in _FORWARD.items():
        EmployeeExpertise.objects.filter(proficiency=old).update(proficiency=new)


def remap_reverse(apps, schema_editor):
    """Reverse the mapping: BEGINNER -> BASIC, SME -> EXPERT.

    REVIEWER has no legacy equivalent; on reverse it is coerced to the closest
    legacy value (EXPERT) so the column remains valid under the old 4-level
    choices. This is documented and only relevant if the whole feature is rolled
    back.
    """
    EmployeeExpertise = apps.get_model("ctx_identity", "EmployeeExpertise")
    for new, old in _REVERSE.items():
        EmployeeExpertise.objects.filter(proficiency=new).update(proficiency=old)
    EmployeeExpertise.objects.filter(proficiency="REVIEWER").update(proficiency="EXPERT")


class Migration(migrations.Migration):

    dependencies = [
        ("ctx_identity", "0004_employee_foundation"),
    ]

    operations = [
        # 1. Additive columns.
        migrations.AddField(
            model_name="employeeexpertise",
            name="skill_id",
            field=models.UUIDField(blank=True, db_index=True, null=True),
        ),
        migrations.AddField(
            model_name="employeeexpertise",
            name="custom_label",
            field=models.CharField(blank=True, max_length=160),
        ),
        migrations.AddField(
            model_name="employeeexpertise",
            name="experience_months",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="employeeexpertise",
            name="certification",
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.AddField(
            model_name="employeeexpertise",
            name="is_primary",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="employeeexpertise",
            name="reviewer_eligible",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="employeeexpertise",
            name="effective_from",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="employeeexpertise",
            name="effective_to",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="employeeexpertise",
            name="is_active",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="employeeexpertise",
            name="evidence",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="employeeexpertise",
            name="last_reviewed_date",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="employeeexpertise",
            name="reviewed_by",
            field=models.UUIDField(blank=True, null=True),
        ),
        # 2. Widen proficiency choices to the five-level vocabulary.
        migrations.AlterField(
            model_name="employeeexpertise",
            name="proficiency",
            field=models.CharField(
                choices=[
                    ("BEGINNER", "Beginner"),
                    ("INTERMEDIATE", "Intermediate"),
                    ("ADVANCED", "Advanced"),
                    ("SME", "Subject matter expert"),
                    ("REVIEWER", "Reviewer"),
                ],
                default="INTERMEDIATE",
                max_length=15,
            ),
        ),
        # 3. Swap the absolute unique for the active-scoped conditional unique.
        migrations.RemoveConstraint(
            model_name="employeeexpertise",
            name="uq_employee_expertise_category",
        ),
        migrations.AddConstraint(
            model_name="employeeexpertise",
            constraint=models.UniqueConstraint(
                fields=("tenant_id", "employee_id", "category"),
                condition=models.Q(is_active=True),
                name="uq_employee_expertise_active_category",
            ),
        ),
        # 4. Reversible, idempotent data remap.
        migrations.RunPython(remap_forward, remap_reverse),
    ]
