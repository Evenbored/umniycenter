from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0001_initial'),
        ('groups', '0002_schoolgroups_is_active'),
        ('schedule', '0006_schedule_students'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Lesson',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('lesson_type', models.CharField(choices=[('group', 'Групповое'), ('individual', 'Индивидуальное'), ('single_group', 'Разовое групповое'), ('single_individual', 'Разовое индивидуальное'), ('trial_group', 'Пробное групповое'), ('trial_individual', 'Пробное индивидуальное')], max_length=32, verbose_name='Тип занятия')),
                ('status', models.CharField(choices=[('scheduled', 'Запланировано'), ('completed', 'Проведено'), ('cancelled', 'Отменено'), ('rescheduled', 'Перенесено')], default='scheduled', max_length=24, verbose_name='Статус')),
                ('starts_at', models.DateTimeField(db_index=True, verbose_name='Начало')),
                ('ends_at', models.DateTimeField(db_index=True, verbose_name='Окончание')),
                ('original_starts_at', models.DateTimeField(blank=True, null=True, verbose_name='Изначальное начало')),
                ('original_ends_at', models.DateTimeField(blank=True, null=True, verbose_name='Изначальное окончание')),
                ('cancel_reason', models.CharField(blank=True, max_length=255, verbose_name='Причина отмены')),
                ('reschedule_reason', models.CharField(blank=True, max_length=255, verbose_name='Причина переноса')),
                ('legacy_schedule_id', models.PositiveIntegerField(blank=True, db_index=True, null=True, verbose_name='Legacy Schedule ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('course', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='lessons', to='courses.courses', verbose_name='Курс')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_lessons', to=settings.AUTH_USER_MODEL, verbose_name='Кто создал')),
                ('group', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='lessons', to='groups.schoolgroups', verbose_name='Группа')),
                ('teacher', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='teacher_lessons', to=settings.AUTH_USER_MODEL, verbose_name='Преподаватель')),
            ],
            options={
                'verbose_name': 'Занятие',
                'verbose_name_plural': 'Занятия',
                'ordering': ['starts_at'],
                'indexes': [models.Index(fields=['starts_at'], name='schedule_le_starts__baf9d0_idx'), models.Index(fields=['status', 'starts_at'], name='schedule_le_status_375573_idx'), models.Index(fields=['teacher', 'starts_at'], name='schedule_le_teacher_17f6e3_idx'), models.Index(fields=['group', 'starts_at'], name='schedule_le_group_i_7aa109_idx'), models.Index(fields=['course', 'starts_at'], name='schedule_le_course__520b82_idx')],
                'constraints': [models.CheckConstraint(check=models.Q(('ends_at__gt', models.F('starts_at'))), name='lesson_ends_after_starts')],
            },
        ),
        migrations.CreateModel(
            name='LessonParticipant',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('attendance_status', models.CharField(choices=[('planned', 'Запланирован'), ('present', 'Присутствовал'), ('absent_charged', 'Отсутствовал, списано'), ('absent_not_charged', 'Отсутствовал, не списано'), ('excused', 'Уважительная причина'), ('canceled', 'Отменено')], default='planned', max_length=32, verbose_name='Статус посещаемости')),
                ('lessons_to_charge', models.PositiveSmallIntegerField(default=0, verbose_name='Списать занятий')),
                ('lessons_charged', models.BooleanField(default=False, verbose_name='Занятия списаны')),
                ('charged_at', models.DateTimeField(blank=True, null=True, verbose_name='Дата списания')),
                ('marked_at', models.DateTimeField(blank=True, null=True, verbose_name='Дата отметки')),
                ('notes', models.TextField(blank=True, verbose_name='Примечания')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('charged_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='charged_lesson_participants', to=settings.AUTH_USER_MODEL, verbose_name='Кто списал')),
                ('lesson', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='participants', to='schedule.lesson', verbose_name='Занятие')),
                ('marked_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='marked_lesson_participants', to=settings.AUTH_USER_MODEL, verbose_name='Кто отметил')),
                ('student', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='lesson_participations', to=settings.AUTH_USER_MODEL, verbose_name='Ученик')),
            ],
            options={
                'verbose_name': 'Участник занятия',
                'verbose_name_plural': 'Участники занятий',
                'indexes': [models.Index(fields=['student', '-created_at'], name='schedule_le_student_fbe113_idx'), models.Index(fields=['lesson', 'attendance_status'], name='schedule_le_lesson__0808b9_idx')],
            },
        ),
    ]
