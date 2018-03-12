"""Define app configuration for results."""

from django.apps import AppConfig


class ResultsConfig(AppConfig):
    """Define app configuration for results."""

    name = 'results'

    def ready(self):
        from . import signals
