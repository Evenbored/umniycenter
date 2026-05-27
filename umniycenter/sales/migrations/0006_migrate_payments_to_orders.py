from django.db import migrations


def migrate_payments_to_orders(apps, schema_editor):
    Payment = apps.get_model('subscriptions', 'Payment')
    Order = apps.get_model('sales', 'Order')
    OrderItem = apps.get_model('sales', 'OrderItem')

    for payment in Payment.objects.select_related('subscription', 'subscription__tariff', 'subscription__student').filter(order__isnull=True).iterator():
        legacy_order = Order.objects.filter(payment_id=payment.id).first()
        subscription = payment.subscription
        if legacy_order:
            order = legacy_order
            if not order.paid_amount:
                order.paid_amount = payment.amount if payment.status == 'completed' else 0
                order.save(update_fields=['paid_amount'])
        else:
            status = 'paid' if payment.status == 'completed' else 'pending_payment'
            if payment.status == 'canceled':
                status = 'canceled'
            elif payment.status == 'refunded':
                status = 'refunded'
            order = Order.objects.create(
                parent_id=payment.parent_id,
                student_id=subscription.student_id if subscription else None,
                status=status,
                payment_id=payment.id,
                total_amount=payment.amount,
                paid_amount=payment.amount if payment.status == 'completed' else 0,
                paid_at=payment.paid_at,
                comment=f'Legacy payment #{payment.id}',
            )
        if subscription:
            OrderItem.objects.get_or_create(
                order=order,
                subscription_id=subscription.id,
                item_type='subscription',
                defaults={
                    'title': subscription.tariff.name,
                    'quantity': 1,
                    'unit_price': payment.amount,
                    'amount': payment.amount,
                    'course_id': subscription.tariff.course_id,
                    'tariff_id': subscription.tariff_id,
                    'metadata': {'legacy_payment_id': payment.id},
                },
            )
        payment.order_id = order.id
        payment.save(update_fields=['order'])


class Migration(migrations.Migration):

    dependencies = [
        ('sales', '0005_legacy_order_payment_related_name'),
        ('subscriptions', '0007_order_payment_refund_new_lesson_log'),
    ]

    operations = [
        migrations.RunPython(migrate_payments_to_orders, migrations.RunPython.noop),
    ]
