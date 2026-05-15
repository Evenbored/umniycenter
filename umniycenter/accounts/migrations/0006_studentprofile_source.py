from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0005_remove_studentprofile_parent_phone'),
    ]

    operations = [
        migrations.AddField(
            model_name='studentprofile',
            name='source',
            field=models.CharField(blank=True, choices=[('poster', 'Афиша'), ('relatives', 'Рассказали родственники'), ('friends', 'Рассказали друзья/знакомые'), ('vk', 'ВК'), ('internet', 'Интернет/поиск'), ('returning', 'Уже занимались раньше'), ('other', 'Другое')], max_length=20, null=True, verbose_name='Источник привлечения'),
        ),
    ]
