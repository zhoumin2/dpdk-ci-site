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

    # Set test run artifacts public IF the test case artifacts are also public
    set_artifacts_public = forms.BooleanField(required=False)

    def form_action(self, environment, user):
        """Submit action."""
        executor.submit(environment.set_public,
                        self.cleaned_data['set_artifacts_public'])

    def save(self, environment, user):
        """Save action."""
        self.form_action(environment, user)


class SetPrivateForm(forms.Form):
    """Set the environment to be private confirmation."""

    # Set test run artifacts private
    set_artifacts_private = forms.BooleanField(required=False)

    def form_action(self, environment, user):
        """Submit action."""
        executor.submit(environment.set_private,
                        self.cleaned_data['set_artifacts_private'])

    def save(self, environment, user):
        """Save action."""
        self.form_action(environment, user)


class SetPublicTestCaseForm(forms.Form):
    """Set the test case to be public."""

    # Set test run artifacts public IF the environments are also public
    set_existing_artifacts_public = forms.BooleanField(required=False)

    def form_action(self, test_case, user):
        executor.submit(test_case.set_public,
                        self.cleaned_data['set_existing_artifacts_public'])

    def save(self, test_case, user):
        self.form_action(test_case, user)


class SetPrivateTestCaseForm(forms.Form):
    """Set the test case to be private."""

    # Set test run artifacts private
    set_existing_artifacts_private = forms.BooleanField(required=False)

    def form_action(self, test_case, user):
        executor.submit(test_case.set_private,
                        self.cleaned_data['set_existing_artifacts_private'])

    def save(self, test_case, user):
        self.form_action(test_case, user)
