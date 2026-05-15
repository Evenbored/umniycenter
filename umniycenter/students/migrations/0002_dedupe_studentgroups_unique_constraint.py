from django.db import migrations, models


def remove_duplicate_student_groups(apps, schema_editor):
    StudentGroups = apps.get_model("students", "StudentGroups")

    duplicates = {}
    for row in StudentGroups.objects.order_by("id").values("id", "group_id", "student_id"):
        key = (row["group_id"], row["student_id"])
        duplicates.setdefault(key, []).append(row["id"])

    duplicate_ids = []
    for ids in duplicates.values():
        duplicate_ids.extend(ids[1:])

    if duplicate_ids:
        StudentGroups.objects.filter(id__in=duplicate_ids).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("students", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(remove_duplicate_student_groups, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name="studentgroups",
            constraint=models.UniqueConstraint(
                fields=("group", "student"),
                name="unique_student_in_group",
            ),
        ),
    ]
