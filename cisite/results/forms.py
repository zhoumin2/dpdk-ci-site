"""Custom forms for the admin interface."""
from django import forms


class SetPublicForm(forms.Form):
    """Set the environment to be public confirmation."""

    def form_action(self, environment, user):
        """Submit action."""
        environment.set_public()

    def save(self, environment, user):
        """Save action."""
        self.form_action(environment, user)


class SetPrivateForm(forms.Form):
    """Set the environment to be private confirmation."""

    def form_action(self, environment, user):
        """Submit action."""
        environment.set_private()

    def save(self, environment, user):
        """Save action."""
        self.form_action(environment, user)
