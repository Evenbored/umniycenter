from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('sales', '0005_legacy_order_payment_related_name'),
        ('subscriptions', '0007_order_payment_refund_new_lesson_log'),
        ('schedule', '0007_lesson_lessonparticipant'),
    ]

    operations = [
        migrations.AddField('lessonparticipant', 'order_item', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='lesson_participations', to='sales.orderitem', verbose_name='Позиция заказа')),
        migrations.AddField('lessonparticipant', 'subscription', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='lesson_participations', to='subscriptions.subscription', verbose_name='Абонемент')),
        migrations.AddIndex('lessonparticipant', models.Index(fields=['subscription'], name='schedule_le_subscri_9a86a0_idx')),
        migrations.AddIndex('lessonparticipant', models.Index(fields=['order_item'], name='schedule_le_order_i_5dcdd4_idx')),
        migrations.AddConstraint('lessonparticipant', models.UniqueConstraint(fields=('lesson', 'student'), name='unique_student_per_lesson')),
    ]
