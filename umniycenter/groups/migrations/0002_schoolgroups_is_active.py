from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("groups", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="schoolgroups",
            name="is_active",
            field=models.BooleanField(default=True, verbose_name="Активная"),
        ),
    ]
