"""Define tests for dashboard app."""

from django.contrib.auth.models import User, Group
from django.test import TestCase
from django.urls import reverse
from results.tests import create_test_environment
from results.models import Subscription

# TODO(DPDKLAB-301): Add unit tests for dashboard views


class PreferencesViewTests(TestCase):
    """Test the preferences view."""

    @classmethod
    def setUpTestData(cls):
        """Set up dummy test data."""
        cls.user1 = User.objects.create_user('joevendor',
                                            'joe@example.com', 'AbCdEfGh')
        cls.user2 = User.objects.create_user('joevendor2',
                                            'joe2@example.com', 'AbCdEfGh2')
        cls.grp1 = Group.objects.create(name='Group1')
        cls.grp2 = Group.objects.create(name='Group2')
        cls.user1.groups.add(cls.grp1)
        cls.user2.groups.add(cls.grp2)

    def test_anonymous_user(self):
        """Test the anonymous user gets redirected to the login page."""
        response = self.client.get(reverse('preferences'))
        self.assertEqual(response.status_code, 302)

    def test_no_env(self):
        """Test the template and returns an empty list."""
        self.client.login(username='joevendor', password='AbCdEfGh')

        response = self.client.get(reverse('preferences'))
        self.assertEqual(response.status_code, 200)
        self.assertQuerysetEqual(response.context['env_sub_pairs'], [])

    def test_with_env(self):
        """Test the template and return a list."""
        create_test_environment(owner=self.__class__.grp1)
        self.client.login(username=self.__class__.user1.username, password='AbCdEfGh')

        response = self.client.get(reverse('preferences'))
        self.assertEqual(response.status_code, 200)
        self.assertQuerysetEqual(response.context['env_sub_pairs'],
            ["{'environment': <Environment: IOL-IOL-1 (v0)>, "
             "'subscription': None}"])

    def test_no_env_available(self):
        """Test the template and returns an empty list.

        Checks that the environment the user does not have access to does not
        show up in the list.
        """
        # Add an environment that the user does not have access to
        create_test_environment(owner=self.__class__.grp2)
        self.client.login(username=self.__class__.user1.username, password='AbCdEfGh')

        response = self.client.get(reverse('preferences'))
        self.assertEqual(response.status_code, 200)
        self.assertQuerysetEqual(response.context['env_sub_pairs'], [])

    def test_env_with_subscription(self):
        """Test the template and return an env:sub pair."""
        env = create_test_environment(owner=self.__class__.grp1)
        Subscription.objects.create(
            user_profile=self.__class__.user1.results_profile, environment=env,
            email_success=False)
        self.client.login(username=self.__class__.user1.username, password='AbCdEfGh')

        response = self.client.get(reverse('preferences'))
        self.assertEqual(response.status_code, 200)
        self.assertQuerysetEqual(response.context['env_sub_pairs'],
            ["{'environment': <Environment: IOL-IOL-1 (v0)>, "
             "'subscription': <Subscription: joevendor: IOL-IOL-1 (v0)>}"])

    def test_env_with_no_subscription(self):
        """Test the template and permissions between subscriptions."""
        # create user3 with access to env
        user = User.objects.create_user('joevendor3',
                                        'joe3@example.com', 'AbCdEfGh3')
        user.groups.add(self.__class__.grp1)
        env = create_test_environment(owner=self.__class__.grp1)
        # create sub with user3
        Subscription.objects.create(
            user_profile=user.results_profile, environment=env,
            email_success=False)
        # but login with user1, who has access to env
        self.client.login(username=self.__class__.user1.username, password='AbCdEfGh')

        response = self.client.get(reverse('preferences'))
        self.assertEqual(response.status_code, 200)
        self.assertQuerysetEqual(response.context['env_sub_pairs'],
            ["{'environment': <Environment: IOL-IOL-1 (v0)>, "
             "'subscription': None}"])
