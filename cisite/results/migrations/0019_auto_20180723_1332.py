# Generated by Django 2.0.6 on 2018-07-23 13:32

from django.db import migrations, models
import django.utils.timezone
import functools
import private_storage.fields
import private_storage.storage.files
import results.models


class Migration(migrations.Migration):

    dependencies = [
        ('results', '0018_auto_20180720_1508'),
    ]

    operations = [
        migrations.AlterField(
            model_name='environment',
            name='date',
            field=models.DateTimeField(default=django.utils.timezone.now, help_text='Date that this version of the environment was added to the test lab', null=True),
        ),
        migrations.AlterField(
            model_name='environment',
            name='hardware_description',
            field=private_storage.fields.PrivateFileField(blank=True, help_text='External hardware description provided by the member. This can include setup configuration, topology, and general hardware environment information.', null=True, storage=private_storage.storage.files.PrivateFileSystemStorage(), upload_to=functools.partial(results.models.upload_model_path, *('hardware_description',), **{})),
        ),
        migrations.AlterField(
            model_name='tarball',
            name='date',
            field=models.DateTimeField(default=django.utils.timezone.now, help_text='When this tarball was generated', null=True),
        ),
    ]
