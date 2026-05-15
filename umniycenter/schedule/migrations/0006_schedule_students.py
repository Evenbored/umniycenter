from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0006_studentprofile_source'),
        ('schedule', '0005_normalize_lesson_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='schedule',
            name='students',
            field=models.ManyToManyField(blank=True, related_name='group_schedules', to='accounts.customuser', verbose_name='Ученики занятия'),
        ),
    ]
