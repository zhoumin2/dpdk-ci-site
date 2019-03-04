"""
SPDX-License-Identifier: BSD-3-Clause
Developed by UNH-IOL dpdklab@iol.unh.edu.

Define app configuration for results.
"""

from django.apps import AppConfig


class ResultsConfig(AppConfig):
    """Define app configuration for results."""

    name = 'results'

    def ready(self):
        """Perform initialization tasks after registry is populated."""
        from . import signals
