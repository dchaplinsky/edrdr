# Generated by Django 2.2.3 on 2019-09-01 15:04

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('companies', '0041_ownedbycompany'),
    ]

    operations = [
        migrations.AddField(
            model_name='companysnapshotflags',
            name='status',
            field=models.IntegerField(choices=[(0, 'інформація відсутня'), (1, 'зареєстровано'), (2, 'припинено'), (3, 'в стані припинення'), (4, 'зареєстровано, свідоцтво про державну реєстрацію недійсне'), (5, 'порушено справу про банкрутство'), (6, 'порушено справу про банкрутство (санація)'), (7, 'розпорядження майном'), (8, 'ліквідація')], default=0, verbose_name='Останій статус компанії'),
        ),
    ]