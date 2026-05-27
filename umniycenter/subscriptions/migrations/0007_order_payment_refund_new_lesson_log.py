from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('schedule', '0007_lesson_lessonparticipant'),
        ('sales', '0003_order_orderitem'),
        ('subscriptions', '0006_subscription_close_fields'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField('payment', 'order', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='payments', to='sales.order', verbose_name='Заказ')),
        migrations.AlterField('payment', 'subscription', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='payments', to='subscriptions.subscription', verbose_name='Подписка (legacy)')),
        migrations.AddField('subscriptionlog', 'related_new_lesson', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='subscription_logs', to='schedule.lesson', verbose_name='Занятие (new)')),
        migrations.CreateModel(
            name='Refund',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('amount', models.DecimalField(decimal_places=2, max_digits=10, verbose_name='Сумма')),
                ('reason', models.TextField(blank=True, verbose_name='Причина')),
                ('status', models.CharField(choices=[('pending', 'Ожидает'), ('completed', 'Выполнен'), ('failed', 'Ошибка'), ('canceled', 'Отменен')], default='pending', max_length=20, verbose_name='Статус')),
                ('external_refund_id', models.CharField(blank=True, max_length=200, null=True, verbose_name='Внешний ID возврата')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_refunds', to=settings.AUTH_USER_MODEL, verbose_name='Кто создал')),
                ('order', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='refunds', to='sales.order', verbose_name='Заказ')),
                ('payment', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='refunds', to='subscriptions.payment', verbose_name='Платеж')),
            ],
            options={'verbose_name': 'Возврат', 'verbose_name_plural': 'Возвраты', 'ordering': ['-created_at']},
        ),
    ]
