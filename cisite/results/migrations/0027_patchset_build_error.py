# Generated by Django 2.0.8 on 2018-10-16 15:13

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('results', '0026_patchset_build_log'),
    ]

    operations = [
        migrations.AddField(
            model_name='patchset',
            name='build_error',
            field=models.BooleanField(default=False, help_text='Was an error encountered trying to build the patch?'),
        ),
    ]
