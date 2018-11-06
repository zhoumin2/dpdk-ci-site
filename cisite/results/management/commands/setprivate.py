"""Implement setprivate command.

This command sets all the results for the environment to be private. This is
to bypass the web interface in case the operation takes too long.
"""

from django.core.management.base import BaseCommand
from results.models import Environment


class Command(BaseCommand):
    """Implement the setprivate command."""

    def add_arguments(self, parser):
        """Arguments for setprivate."""
        parser.add_argument('--env', type=int, required=True,
                            help='The environment id to set private.')

    def handle(self, *args, **options):
        """Perform the migration."""
        env = options['env']
        qs = Environment.objects.get(pk=env)
        qs.set_private()
