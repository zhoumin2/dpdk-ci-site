# Generated by Django 2.2 on 2019-04-10 20:53

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('results', '0031_branch_web_url'),
    ]

    operations = [
        migrations.AddField(
            model_name='testcase',
            name='pipeline',
            field=models.CharField(blank=True, help_text='The pipeline name used for running tests. This is combinedwith the pipeline name of the environment.', max_length=255, null=True),
        ),
        migrations.AlterField(
            model_name='environment',
            name='pipeline',
            field=models.CharField(blank=True, help_text='The pipeline name used for running tests. This is combinedwith the pipeline name of the test case.', max_length=255, null=True),
        ),
    ]
