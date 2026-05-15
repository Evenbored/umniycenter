import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0006_studentprofile_source'),
        ('courses', '0001_initial'),
        ('schedule', '0003_alter_schedule_status'),
    ]

    operations = [
        migrations.AddField(
            model_name='schedule',
            name='course',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='courses.courses', verbose_name='Курс'),
        ),
        migrations.AddField(
            model_name='schedule',
            name='is_single',
            field=models.BooleanField(default=False, verbose_name='Разовое занятие'),
        ),
        migrations.AddField(
            model_name='schedule',
            name='lesson_type',
            field=models.CharField(choices=[('group', 'Групповое занятие'), ('individual', 'Индивидуальное занятие'), ('single', 'Разовое занятие')], default='group', max_length=20, verbose_name='Тип занятия'),
        ),
        migrations.AddField(
            model_name='schedule',
            name='student',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='individual_schedules', to='accounts.customuser', verbose_name='Ученик'),
        ),
        migrations.AlterField(
            model_name='schedule',
            name='group',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='groups.schoolgroups', verbose_name='Группа'),
        ),
    ]
