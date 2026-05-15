from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0005_change_request_to_phone_and_courses'),
    ]

    operations = [
        migrations.AddField(
            model_name='participantrequest',
            name='source',
            field=models.CharField(blank=True, choices=[('poster', 'Афиша'), ('relatives', 'Рассказали родственники'), ('friends', 'Рассказали друзья/знакомые'), ('vk', 'ВК'), ('internet', 'Интернет/поиск'), ('returning', 'Уже занимались раньше'), ('other', 'Другое')], max_length=20, null=True, verbose_name='Как узнали о центре'),
        ),
    ]
