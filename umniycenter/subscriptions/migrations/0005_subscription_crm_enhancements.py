from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0001_initial'),
        ('groups', '0001_initial'),
        ('schedule', '0001_initial'),
        ('subscriptions', '0004_tariff_subscription_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='tariff',
            name='allow_negative_lessons',
            field=models.BooleanField(default=False, verbose_name='Разрешить занятия в минус'),
        ),
        migrations.AddField(
            model_name='tariff',
            name='default_negative_limit',
            field=models.PositiveSmallIntegerField(default=0, verbose_name='Лимит занятий в минус'),
        ),
        migrations.AddField(
            model_name='tariff',
            name='allow_group_to_individual',
            field=models.BooleanField(default=False, verbose_name='Разрешить использовать групповой абонемент для индивидуальных занятий'),
        ),
        migrations.AddField(
            model_name='tariff',
            name='group_to_individual_ratio',
            field=models.PositiveSmallIntegerField(default=2, verbose_name='Сколько групповых занятий списывать за 1 индивидуальное'),
        ),
        migrations.AddField(
            model_name='subscription',
            name='group',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='subscriptions', to='groups.schoolgroups', verbose_name='Группа'),
        ),
        migrations.AddField(
            model_name='subscription',
            name='frozen_until',
            field=models.DateField(blank=True, null=True, verbose_name='Заморожен до'),
        ),
        migrations.AddField(
            model_name='subscription',
            name='freeze_reason',
            field=models.CharField(blank=True, max_length=255, verbose_name='Причина заморозки'),
        ),
        migrations.AddField(
            model_name='subscription',
            name='allow_negative_lessons',
            field=models.BooleanField(default=False, verbose_name='Разрешить занятия в минус'),
        ),
        migrations.AddField(
            model_name='subscription',
            name='negative_limit',
            field=models.PositiveSmallIntegerField(default=0, verbose_name='Лимит занятий в минус'),
        ),
        migrations.AddField(
            model_name='subscription',
            name='allow_group_to_individual',
            field=models.BooleanField(default=False, verbose_name='Можно тратить на индивидуальные'),
        ),
        migrations.AddField(
            model_name='subscription',
            name='group_to_individual_ratio',
            field=models.PositiveSmallIntegerField(default=2, verbose_name='Коэффициент индивидуального занятия'),
        ),
        migrations.CreateModel(
            name='SubscriptionFreeze',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('start_date', models.DateField(verbose_name='Дата начала')),
                ('end_date', models.DateField(verbose_name='Дата окончания')),
                ('days', models.PositiveSmallIntegerField(verbose_name='Количество дней')),
                ('reason', models.CharField(blank=True, max_length=255, verbose_name='Причина')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_subscription_freezes', to='accounts.customuser', verbose_name='Кто создал')),
                ('subscription', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='freezes', to='subscriptions.subscription', verbose_name='Абонемент')),
            ],
            options={
                'verbose_name': 'Заморозка абонемента',
                'verbose_name_plural': 'Заморозки абонементов',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='SubscriptionLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('action', models.CharField(choices=[('created', 'Создан'), ('activated', 'Активирован'), ('deduct', 'Списаны занятия'), ('refund', 'Возвращены занятия'), ('freeze', 'Заморожен'), ('unfreeze', 'Разморожен'), ('group_assigned', 'Привязан к группе'), ('manual_group_add', 'Ручное добавление в группу'), ('negative_limit_changed', 'Изменен лимит минуса')], max_length=40, verbose_name='Действие')),
                ('lessons_delta', models.IntegerField(default=0, verbose_name='Изменение занятий')),
                ('balance_after', models.IntegerField(default=0, verbose_name='Остаток после операции')),
                ('comment', models.TextField(blank=True, verbose_name='Комментарий')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='subscription_logs', to='accounts.customuser', verbose_name='Кто выполнил')),
                ('related_lesson', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='subscription_logs', to='schedule.schedule', verbose_name='Занятие')),
                ('subscription', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='logs', to='subscriptions.subscription', verbose_name='Абонемент')),
            ],
            options={
                'verbose_name': 'Операция по абонементу',
                'verbose_name_plural': 'Операции по абонементам',
                'ordering': ['-created_at'],
            },
        ),
    ]
