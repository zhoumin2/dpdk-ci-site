# Generated by Django 2.0.8 on 2018-09-12 18:23

# Modified migration file, see migration 0021 for more info.

from django.db import migrations, models
import uuid


def gen_uuid(apps, schema_editor):
    db_alias = schema_editor.connection.alias
    PatchSet = apps.get_model('results', 'PatchSet')
    for row in PatchSet.objects.using(db_alias).all():
        row.uuid = uuid.uuid4()
        row.save(update_fields=['uuid'])


class Migration(migrations.Migration):

    dependencies = [
        ('results', '0024_environment_pipeline'),
    ]

    operations = [
        migrations.AddField(
            model_name='patchset',
            name='uuid',
            field=models.UUIDField(default=uuid.uuid4, editable=False, null=True),
        ),
        migrations.RunPython(gen_uuid, reverse_code=migrations.RunPython.noop),
        migrations.AlterField(
            model_name='patchset',
            name='uuid',
            field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
        ),
    ]
