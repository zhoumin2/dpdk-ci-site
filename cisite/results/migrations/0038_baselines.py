# Generated by Django 2.2.4 on 2020-01-09 20:47
"""
Creates the baseline field and populates the field based on the removed branch
and commit_id fields.
"""

from django.db import migrations, models
import django.db.models.deletion


def convert_to_baseline(apps, schema_editor):
    db_alias = schema_editor.connection.alias
    TestRun = apps.get_model('results', 'TestRun')
    Tarball = apps.get_model('results', 'Tarball')
    Branch = apps.get_model('results', 'Branch')
    master = Branch.objects.first()

    # This removes db entries that do not contain both a branch and a commit id
    # (old entries, test cases unrelated to performance)
    for row in TestRun.objects.using(db_alias).exclude(branch=None, commit_id=''):
        # but we still need to deal with either a branch or commit having a
        # value, which might be a data loss issue - so tell the user.
        if not row.commit_id:
            print(f'Warning: TestRun {row.id}: The commit_id is not set! A '
                  'baseline will not be added.')
            continue

        if row.branch:
            branch = row.branch
        else:
            print(f'TestRun {row.id}: The branch is not set! '
                  'Assuming branch id 1.')
            branch = master

        tarballs = Tarball.objects.filter(
            branch=branch, commit_id=row.commit_id, patchset=None)

        # Get the most recent tarball
        tarball = tarballs.last()

        if tarballs.count() > 1:
            ids = tarballs.values_list('id', flat=True)
            print(f'TestRun {row.id}: Multiple tarballs applicable ({ids}). '
                  f'Using latest tarball ({tarball.id}).')

        # Now we need to match the previous test runs associated with the
        # tarball based on the environment and test case of the current
        # test run
        test_runs = tarball.runs.filter(
            environment=row.environment, testcase=row.testcase)

        if not test_runs:
            print(f'TestRun {row.id}: A baseline cannot be determined since '
                  f'there are no valid past test runs (tarball {tarball.id}). '
                  'This may be a new environment or test case.')
            continue

        baseline = test_runs.last()

        if test_runs.count() > 1:
            ids = test_runs.values_list('id', flat=True)
            print(f'TestRun {row.id}: Multiple baselines applicable ({ids}). '
                  f'Using latest baseline ({baseline.id}).')

        row.baseline = baseline

        row.save(update_fields=['baseline'])


class Migration(migrations.Migration):

    dependencies = [
        ('results', '0037_auto_20190722_1520'),
    ]

    operations = [
        migrations.AddField(
            model_name='testrun',
            name='baseline',
            field=models.ForeignKey(blank=True, help_text='The baseline results used for performance tests', null=True, on_delete=django.db.models.deletion.SET_NULL, to='results.TestRun'),
        ),
        migrations.RunPython(convert_to_baseline, reverse_code=migrations.RunPython.noop),
        migrations.RemoveField(
            model_name='testrun',
            name='branch',
        ),
        migrations.RemoveField(
            model_name='testrun',
            name='commit_id',
        ),
    ]
