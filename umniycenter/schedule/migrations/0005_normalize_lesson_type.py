from django.db import migrations, models


def normalize_lesson_type(apps, schema_editor):
    Schedule = apps.get_model('schedule', 'Schedule')
    Schedule.objects.filter(lesson_type__in=['group', 'individual']).update(lesson_type='regular', is_single=False)
    Schedule.objects.filter(lesson_type='single').update(is_single=True)


class Migration(migrations.Migration):

    dependencies = [
        ('schedule', '0004_individual_and_single_lessons'),
    ]

    operations = [
        migrations.RunPython(normalize_lesson_type, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='schedule',
            name='lesson_type',
            field=models.CharField(choices=[('regular', 'Постоянное занятие'), ('single', 'Разовое занятие')], default='regular', max_length=20, verbose_name='Тип занятия'),
        ),
    ]
