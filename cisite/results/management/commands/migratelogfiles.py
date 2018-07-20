"""Implement migratelogfiles command.

This command migrates logs from Jenkins to Django's private file storage.
"""

import os
from urllib.parse import urlparse
from http import HTTPStatus
import requests
from django.conf import settings
from django.core.management.base import BaseCommand
from results.models import TestRun, upload_model_path


class Command(BaseCommand):
    """Implement the migratelogfiles command."""

    def add_arguments(self, parser):
        """Add arguments for username/password to Jenkins."""
        parser.add_argument('--jenkins-user', type=str)
        parser.add_argument('--jenkins-api-token', type=str)
        parser.add_argument('--cacert', type=str)

    def handle(self, *args, **options):
        """Perform the migration."""
        session = requests.Session()
        if options.get('cacert'):
            session.verify = options['cacert']
        qs = TestRun.objects.filter(log_output_file__isnull=False,
                                    log_upload_file__isnull=True)
        for run in qs.iterator():
            url = run.log_output_file
            if options.get('verbosity', False):
                self.stdout.write(f'/testruns/{run.id}/: Migrating {url}')
            resp = session.get(url, auth=(options['jenkins_user'],
                                          options['jenkins_api_token']))
            if resp.status_code >= HTTPStatus.BAD_REQUEST:
                self.stderr.write(f'Error {resp.status_code} fetching {url}')
                continue
            name = upload_model_path('log_upload_file', run,
                                     os.path.basename(urlparse(url).path))
            fullpath = os.path.join(settings.PRIVATE_STORAGE_ROOT, name)
            os.makedirs(os.path.dirname(fullpath), exist_ok=True)
            with open(fullpath, 'wb') as fp:
                fp.write(resp.content)
            run.log_upload_file = name
            run.save()
