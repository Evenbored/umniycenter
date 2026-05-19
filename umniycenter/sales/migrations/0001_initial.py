from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('courses', '0001_initial'),
        ('main', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Lead',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('parent_fio', models.CharField(max_length=150, verbose_name='ФИО родителя')),
                ('child_fio', models.CharField(max_length=150, verbose_name='ФИО ребенка')),
                ('phone', models.CharField(max_length=20, verbose_name='Телефон')),
                ('email', models.EmailField(blank=True, max_length=254, null=True, verbose_name='Email')),
                ('age', models.CharField(blank=True, max_length=3, verbose_name='Возраст ребенка')),
                ('source', models.CharField(blank=True, choices=[('poster', 'Афиша'), ('relatives', 'Рассказали родственники'), ('friends', 'Рассказали друзья/знакомые'), ('vk', 'ВК'), ('internet', 'Интернет/поиск'), ('returning', 'Уже занимались раньше'), ('other', 'Другое')], max_length=20, null=True, verbose_name='Источник')),
                ('status', models.CharField(choices=[('new', 'Новая'), ('in_progress', 'В работе'), ('no_answer', 'Не дозвонились'), ('contacted', 'Контакт установлен'), ('trial_scheduled', 'Пробное назначено'), ('trial_completed', 'Пробное проведено'), ('waiting_decision', 'Клиент думает'), ('converted', 'Купил абонемент'), ('lost', 'Отказ'), ('archived', 'Архив')], default='new', max_length=32, verbose_name='Статус')),
                ('next_contact_at', models.DateTimeField(blank=True, null=True, verbose_name='Следующий контакт')),
                ('last_contact_at', models.DateTimeField(blank=True, null=True, verbose_name='Последний контакт')),
                ('lost_reason', models.CharField(blank=True, max_length=255, verbose_name='Причина отказа')),
                ('comment', models.TextField(blank=True, verbose_name='Комментарий')),
                ('converted_at', models.DateTimeField(blank=True, null=True, verbose_name='Дата конвертации')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Дата обновления')),
                ('assigned_to', models.ForeignKey(blank=True, limit_choices_to={'role': 2}, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='assigned_leads', to=settings.AUTH_USER_MODEL, verbose_name='Ответственный')),
                ('converted_parent', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='converted_leads_as_parent', to=settings.AUTH_USER_MODEL, verbose_name='Созданный родитель')),
                ('converted_student', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='converted_leads_as_student', to=settings.AUTH_USER_MODEL, verbose_name='Созданный ученик')),
                ('courses', models.ManyToManyField(blank=True, related_name='leads', to='courses.courses', verbose_name='Интересующие курсы')),
                ('participant_request', models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='lead', to='main.participantrequest', verbose_name='Исходная заявка')),
            ],
            options={
                'verbose_name': 'Лид',
                'verbose_name_plural': 'Лиды',
                'ordering': ['-created_at'],
                'indexes': [models.Index(fields=['status', '-created_at'], name='sales_lead_status_20fd90_idx'), models.Index(fields=['assigned_to', 'status'], name='sales_lead_assigne_9d63c7_idx'), models.Index(fields=['next_contact_at'], name='sales_lead_next_co_2cdd31_idx'), models.Index(fields=['source'], name='sales_lead_source_e407f2_idx')],
            },
        ),
    ]
