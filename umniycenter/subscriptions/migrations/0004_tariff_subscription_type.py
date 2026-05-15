from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('subscriptions', '0003_alter_subscription_status'),
    ]

    operations = [
        migrations.AddField(
            model_name='tariff',
            name='subscription_type',
            field=models.CharField(choices=[('group', 'Групповой абонемент'), ('individual', 'Индивидуальный абонемент')], default='group', max_length=20, verbose_name='Тип абонемента'),
        ),
    ]
