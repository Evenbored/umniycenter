from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0001_initial'),
        ('schedule', '0005_normalize_lesson_type'),
        ('subscriptions', '0001_initial'),
        ('sales', '0002_rename_sales_lead_status_20fd90_idx_sales_lead_status_4b2468_idx_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Order',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(choices=[('draft', 'Черновик'), ('pending', 'Ожидает оплаты'), ('paid', 'Оплачен'), ('canceled', 'Отменен'), ('refunded', 'Возврат')], default='pending', max_length=24, verbose_name='Статус')),
                ('total_amount', models.DecimalField(decimal_places=2, default=0, max_digits=10, verbose_name='Сумма')),
                ('paid_at', models.DateTimeField(blank=True, null=True, verbose_name='Дата оплаты')),
                ('comment', models.TextField(blank=True, verbose_name='Комментарий')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_sales_orders', to=settings.AUTH_USER_MODEL, verbose_name='Кто создал')),
                ('parent', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='sales_orders', to=settings.AUTH_USER_MODEL, verbose_name='Покупатель')),
                ('payment', models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='legacy_order', to='subscriptions.payment', verbose_name='Связанный платеж абонемента')),
                ('student', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='student_sales_orders', to=settings.AUTH_USER_MODEL, verbose_name='Ученик')),
            ],
            options={
                'verbose_name': 'Заказ/продажа',
                'verbose_name_plural': 'Заказы/продажи',
                'ordering': ['-created_at'],
                'indexes': [models.Index(fields=['status', '-created_at'], name='sales_order_status_4c8d9e_idx'), models.Index(fields=['paid_at'], name='sales_order_paid_at_1a5d4b_idx')],
            },
        ),
        migrations.CreateModel(
            name='OrderItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('item_type', models.CharField(choices=[('subscription', 'Абонемент'), ('single_group', 'Групповое разовое занятие'), ('single_individual', 'Индивидуальное разовое занятие'), ('product', 'Товар'), ('rent', 'Аренда'), ('account_topup', 'Пополнение лицевого счета')], max_length=32, verbose_name='Тип позиции')),
                ('title', models.CharField(max_length=255, verbose_name='Название')),
                ('amount', models.DecimalField(decimal_places=2, max_digits=10, verbose_name='Сумма')),
                ('quantity', models.PositiveIntegerField(default=1, verbose_name='Количество')),
                ('metadata', models.JSONField(blank=True, default=dict, verbose_name='Дополнительные данные')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('course', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='order_items', to='courses.courses', verbose_name='Курс')),
                ('order', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='items', to='sales.order', verbose_name='Заказ')),
                ('schedule', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='order_items', to='schedule.schedule', verbose_name='Занятие')),
                ('subscription', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='order_items', to='subscriptions.subscription', verbose_name='Абонемент')),
                ('tariff', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='order_items', to='subscriptions.tariff', verbose_name='Тариф')),
            ],
            options={
                'verbose_name': 'Позиция заказа',
                'verbose_name_plural': 'Позиции заказов',
                'ordering': ['id'],
                'indexes': [models.Index(fields=['item_type', 'created_at'], name='sales_order_item_ty_99da03_idx'), models.Index(fields=['schedule'], name='sales_order_schedul_d5481a_idx'), models.Index(fields=['subscription'], name='sales_order_subscri_8b1332_idx')],
            },
        ),
    ]
