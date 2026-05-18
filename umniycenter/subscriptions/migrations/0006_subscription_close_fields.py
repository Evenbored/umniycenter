from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0001_initial'),
        ('subscriptions', '0005_subscription_crm_enhancements'),
    ]

    operations = [
        migrations.AddField(
            model_name='subscription',
            name='closed_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Дата закрытия'),
        ),
        migrations.AddField(
            model_name='subscription',
            name='closed_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='closed_subscriptions', to='accounts.customuser', verbose_name='Кто закрыл'),
        ),
        migrations.AddField(
            model_name='subscription',
            name='close_reason',
            field=models.TextField(blank=True, verbose_name='Причина закрытия'),
        ),
        migrations.AlterField(
            model_name='subscription',
            name='status',
            field=models.CharField(choices=[('pending', 'Ожидает оплаты'), ('active', 'Активный'), ('expired', 'Истек срок'), ('exhausted', 'Исчерпан'), ('frozen', 'Заморожен'), ('canceled', 'Отменен'), ('completed', 'Завершен вручную')], default='pending', max_length=20, verbose_name='Статус'),
        ),
        migrations.AlterField(
            model_name='subscriptionlog',
            name='action',
            field=models.CharField(choices=[('created', 'Создан'), ('activated', 'Активирован'), ('deduct', 'Списаны занятия'), ('refund', 'Возвращены занятия'), ('freeze', 'Заморожен'), ('unfreeze', 'Разморожен'), ('canceled', 'Отменен'), ('completed', 'Завершен вручную'), ('expired', 'Истек срок'), ('exhausted', 'Исчерпан'), ('group_assigned', 'Привязан к группе'), ('manual_group_add', 'Ручное добавление в группу'), ('negative_limit_changed', 'Изменен лимит минуса')], max_length=40, verbose_name='Действие'),
        ),
    ]
