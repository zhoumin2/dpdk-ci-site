# Generated by Django 2.2 on 2019-05-20 15:38

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('results', '0032_auto_20190410_2053'),
    ]

    operations = [
        migrations.AddField(
            model_name='testrun',
            name='testcase',
            field=models.ForeignKey(blank=True, help_text='Test case that this test run applies to', null=True, on_delete=django.db.models.deletion.CASCADE, to='results.TestCase'),
        ),
    ]
