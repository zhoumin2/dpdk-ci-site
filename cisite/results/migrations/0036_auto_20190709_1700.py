# Generated by Django 2.2.2 on 2019-07-09 17:00

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('results', '0035_vendor'),
    ]

    operations = [
        migrations.AddField(
            model_name='environment',
            name='alternate_name',
            field=models.CharField(blank=True, help_text='Alternate name to display instead of the nic details', max_length=255),
        ),
        migrations.AlterField(
            model_name='testresult',
            name='difference',
            field=models.FloatField(blank=True, help_text='Difference between actual and expected values', null=True),
        ),
        migrations.AlterField(
            model_name='testresult',
            name='measurement',
            field=models.ForeignKey(help_text='Vendor expected measurement that this result corresponds to', null=True, on_delete=django.db.models.deletion.CASCADE, to='results.Measurement'),
        ),
    ]
