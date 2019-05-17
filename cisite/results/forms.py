"""
SPDX-License-Identifier: BSD-3-Clause
Developed by UNH-IOL dpdklab@iol.unh.edu.

Custom forms for the admin interface.
"""
from concurrent.futures.thread import ThreadPoolExecutor

from django import forms

# 1 worker so that set_private and set_public can't be executed at the same time
executor = ThreadPoolExecutor(max_workers=1)


class SetPublicForm(forms.Form):
    """Set the environment to be public confirmation."""

    def form_action(self, environment, user):
        """Submit action."""
        executor.submit(environment.set_public)

    def save(self, environment, user):
        """Save action."""
        self.form_action(environment, user)


class SetPrivateForm(forms.Form):
    """Set the environment to be private confirmation."""

    def form_action(self, environment, user):
        """Submit action."""
        executor.submit(environment.set_private)

    def save(self, environment, user):
        """Save action."""
        self.form_action(environment, user)
