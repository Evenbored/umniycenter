from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('subscriptions', '0007_order_payment_refund_new_lesson_log'),
        ('sales', '0004_order_paid_amount_item_lesson_unit_price'),
    ]

    operations = [
        migrations.AlterField(
            model_name='order',
            name='payment',
            field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='legacy_order', to='subscriptions.payment', verbose_name='Связанный платеж абонемента'),
        ),
    ]
