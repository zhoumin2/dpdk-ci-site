"""Define dashboard Django application configuration."""

from django.apps import AppConfig


class DashboardConfig(AppConfig):
    name = 'dashboard'

    def ready(self):
        """Import signals."""
        from . import signals
