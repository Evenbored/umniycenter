from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('schedule', '0007_lesson_lessonparticipant'),
        ('sales', '0003_order_orderitem'),
    ]

    operations = [
        migrations.AddField('order', 'paid_amount', models.DecimalField(decimal_places=2, default=0, max_digits=10, verbose_name='Оплачено')),
        migrations.AddField('orderitem', 'lesson', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='order_items', to='schedule.lesson', verbose_name='Занятие (new)')),
        migrations.AddField('orderitem', 'unit_price', models.DecimalField(decimal_places=2, default=0, max_digits=10, verbose_name='Цена за единицу')),
        migrations.AddIndex('orderitem', models.Index(fields=['lesson'], name='sales_order_lesson__308c6b_idx')),
        migrations.AlterField('order', 'status', models.CharField(choices=[('draft', 'Черновик'), ('pending', 'Ожидает оплаты'), ('pending_payment', 'Ожидает оплаты'), ('partially_paid', 'Частично оплачен'), ('paid', 'Оплачен'), ('canceled', 'Отменен'), ('refunded', 'Возврат')], default='pending', max_length=24, verbose_name='Статус')),
    ]
