# Generated by Django 2.0 on 2018-04-27 20:14

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('results', '0004_auto_20180410_1741'),
    ]

    operations = [
        migrations.AddField(
            model_name='contactpolicy',
            name='email_success',
            field=models.BooleanField(default=True, help_text='Set to false to send only reports of failures'),
        ),
    ]
