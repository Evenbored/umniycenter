from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('communication', '0001_initial'),
        ('sales', '0001_initial'),
        ('schedule', '0001_initial'),
        ('subscriptions', '0006_subscription_close_fields'),
    ]

    operations = [
        migrations.CreateModel(
            name='Task',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=200, verbose_name='Название')),
                ('description', models.TextField(blank=True, verbose_name='Описание')),
                ('task_type', models.CharField(choices=[('call', 'Звонок'), ('message', 'Сообщение'), ('payment', 'Оплата'), ('renewal', 'Продление абонемента'), ('trial', 'Пробное занятие'), ('absence', 'Пропуск занятия'), ('schedule', 'Расписание'), ('document', 'Документ'), ('other', 'Другое')], default='other', max_length=24, verbose_name='Тип')),
                ('status', models.CharField(choices=[('new', 'Новая'), ('in_progress', 'В работе'), ('done', 'Выполнена'), ('canceled', 'Отменена')], default='new', max_length=24, verbose_name='Статус')),
                ('priority', models.CharField(choices=[('low', 'Низкий'), ('medium', 'Средний'), ('high', 'Высокий')], default='medium', max_length=16, verbose_name='Приоритет')),
                ('due_at', models.DateTimeField(blank=True, null=True, verbose_name='Срок выполнения')),
                ('completed_at', models.DateTimeField(blank=True, null=True, verbose_name='Дата завершения')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('assignee', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='assigned_tasks', to=settings.AUTH_USER_MODEL, verbose_name='Ответственный')),
                ('author', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_tasks', to=settings.AUTH_USER_MODEL, verbose_name='Автор')),
                ('lead', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='tasks', to='sales.lead', verbose_name='Лид')),
                ('student', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='student_tasks', to=settings.AUTH_USER_MODEL, verbose_name='Ученик')),
                ('parent', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='parent_tasks', to=settings.AUTH_USER_MODEL, verbose_name='Родитель')),
                ('payment', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='tasks', to='subscriptions.payment', verbose_name='Платеж')),
                ('subscription', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='tasks', to='subscriptions.subscription', verbose_name='Абонемент')),
                ('lesson', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='tasks', to='schedule.schedule', verbose_name='Занятие')),
                ('ticket', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='tasks', to='communication.ticket', verbose_name='Обращение')),
            ],
            options={
                'verbose_name': 'Задача',
                'verbose_name_plural': 'Задачи',
                'ordering': ['status', 'due_at', '-created_at'],
                'indexes': [models.Index(fields=['assignee', 'status', 'due_at'], name='tasks_task_assigne_495f98_idx'), models.Index(fields=['status', 'due_at'], name='tasks_task_status_58dbd7_idx'), models.Index(fields=['task_type'], name='tasks_task_task_ty_5656a6_idx')],
            },
        ),
    ]
