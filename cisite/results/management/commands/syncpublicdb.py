"""
SPDX-License-Identifier: BSD-3-Clause
Developed by UNH-IOL dpdklab@iol.unh.edu.

Implement syncpublicdb command.

This command will sync public results by flushing the public database, then
syncing public models from the default database to the public database.
"""

import tempfile
import warnings

from django.apps import apps
from django.core import serializers
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.core.management.commands.dumpdata import ProxyModelWarning
from django.db import DEFAULT_DB_ALIAS, router
from guardian.shortcuts import get_objects_for_user
from guardian.utils import get_anonymous_user


class Command(BaseCommand):
    help = (
        "Sync the default database with the public database."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '-o', '--output',
            help='Specifies file to which the output is written (yaml).'
                 'Note: This is a dry run command to debug the structure of'
                 'the fixture.'
        )

    def handle(self, *app_labels, **options):
        output = options['output']
        if output:
            with open(output, mode='w') as f:
                self.get_data(f)
        else:
            # Cannot be in binary mode when writing with serializer.
            # loaddata command detects file type by file extension.
            with tempfile.NamedTemporaryFile(mode='w+', suffix='.yaml') as temp_file:
                self.get_data(temp_file)
                self.flush_db()
                self.load_data(temp_file)

    def get_data(self, temp_file):
        # NOTE: keep in mind that models are manually ordered by their
        # dependencies because `serializers.sort_dependencies` did not work.
        models = []
        # Select only the results app
        results_app_config = apps.get_app_config('results')
        # But we depend on the group model from auth as well
        auth_app_config = apps.get_app_config('auth')

        # Grab the group model from auth
        model = auth_app_config.get_model('group')
        models.append(model)

        # Select only specific models we care about from results
        for model_name in ['branch', 'testcase', 'environment', 'tarball',
                           'measurement', 'testrun', 'patchset', 'testresult']:
            model = results_app_config.get_model(model_name)
            models.append(model)

        self.stdout.ending = None
        serializers.serialize('yaml', self.get_objects(models),
                              stream=temp_file)

    def get_objects(self, models):
        """Collate the objects to be serialized."""
        for model in models:
            if model._meta.proxy and model._meta.proxy_for_model not in models:
                warnings.warn(
                    f'{model._meta.label} is a proxy model and won\'t be serialized.',
                    category=ProxyModelWarning,
                )
            if not model._meta.proxy and \
                    router.allow_migrate_model(DEFAULT_DB_ALIAS, model):
                # Now check if the anonymous user can see results. The
                # "default" case (the else) is for models to have permissions,
                # so if something changes in the future, then a model without
                # permissions must be added to this if statement list. This is
                # to hopefully avoid possible data leaks when new models are
                # added that require permissions, hence it will "fail-safe"
                # into checking for permissions.
                if model._meta.model_name in ['branch', 'group', 'testcase',
                                              'tarball', 'patchset']:
                    objects = model._default_manager
                else:
                    objects = get_objects_for_user(
                        get_anonymous_user(),
                        'results.view_' + model._meta.model_name)

                queryset = objects.using(DEFAULT_DB_ALIAS).order_by(model._meta.pk.name)
                yield from queryset.iterator()

    def flush_db(self):
        call_command('flush', interactive=False, database='public')

    def load_data(self, temp_file):
        call_command('loaddata', temp_file.name, database='public')
