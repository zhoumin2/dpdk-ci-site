"""
SPDX-License-Identifier: BSD-3-Clause
Developed by UNH-IOL dpdklab@iol.unh.edu.

Implement setpublic command.

This command sets all the results for the environment to be public. This is
to bypass the web interface in case the operation takes too long.
"""

from django.core.management.base import BaseCommand
from results.models import Environment


class Command(BaseCommand):
    """Implement the setpublic command."""

    def add_arguments(self, parser):
        """Arguments for setpublic."""
        parser.add_argument('--env', type=int, required=True,
                            help='The environment id to set public.')

    def handle(self, *args, **options):
        """Perform the migration."""
        env = options['env']
        qs = Environment.objects.get(pk=env)
        qs.set_public()
