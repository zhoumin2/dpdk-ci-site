# Generated by Django 2.0 on 2018-04-10 16:46

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('results', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='environment',
            name='nic_speed',
            field=models.PositiveIntegerField(default=10000, help_text='Speed of NIC link(s) used for testing'),
        ),
    ]
