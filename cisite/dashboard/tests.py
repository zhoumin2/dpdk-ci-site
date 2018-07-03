"""Define tests for dashboard app."""

from django.contrib.auth.models import User, Group
from django.contrib.contenttypes.models import ContentType
from django.test import LiveServerTestCase
from django.urls import reverse
from results.tests import create_test_environment
from results.models import Subscription

# TODO(DPDKLAB-301): Add unit tests for dashboard views


class PreferencesViewTests(LiveServerTestCase):
    """Test the preferences view."""

    def setUp(self):
        """Set up dummy test data."""
        super().setUp()
        self.user1 = User.objects.create_user('joevendor',
                                              'joe@example.com',
                                              'AbCdEfGh')
        self.user2 = User.objects.create_user('joevendor2',
                                              'joe2@example.com',
                                              'AbCdEfGh2')
        self.grp1 = Group.objects.create(name='Group1')
        self.grp2 = Group.objects.create(name='Group2')
        self.user1.groups.add(self.grp1)
        self.user2.groups.add(self.grp2)

    def tearDown(self):
        """Clear cache to fix an IntegrityError bug."""
        ContentType.objects.clear_cache()
        super().tearDown()

    def test_anonymous_user(self):
        """Test the anonymous user gets redirected to the login page."""
        response = self.client.get(reverse('preferences'))
        self.assertEqual(response.status_code, 302)

    def test_no_env(self):
        """Test the template and returns an empty list."""
        with self.settings(API_BASE_URL=self.live_server_url):
            response = self.client.post(reverse('login'),
                dict(username=self.user1.username, password='AbCdEfGh'), follow=True)
            self.assertTrue(response.context['user'].is_active)

            response = self.client.get(reverse('preferences'))

        self.assertEqual(response.status_code, 200)
        self.assertQuerysetEqual(response.context['env_sub_pairs'], [])

    def test_with_env(self):
        """Test the template and return a list."""
        env = create_test_environment(owner=self.grp1)

        with self.settings(API_BASE_URL=self.live_server_url):
            response = self.client.post(reverse('login'),
                dict(username=self.user1.username, password='AbCdEfGh'), follow=True)
            self.assertTrue(response.context['user'].is_active)

            response = self.client.get(reverse('preferences'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['env_sub_pairs'][0]['environment']['id'], env.id)
        self.assertEqual(response.context['env_sub_pairs'][0]['subscription'], None)

    def test_no_env_available(self):
        """Test the template and returns an empty list.

        Checks that the environment the user does not have access to does not
        show up in the list.
        """
        # Add an environment that the user does not have access to
        create_test_environment(owner=self.grp2)

        with self.settings(API_BASE_URL=self.live_server_url):
            response = self.client.post(reverse('login'),
                dict(username=self.user1.username, password='AbCdEfGh'), follow=True)
            self.assertTrue(response.context['user'].is_active)

            response = self.client.get(reverse('preferences'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['env_sub_pairs'], [])

    def test_env_with_subscription(self):
        """Test the template and return an env:sub pair."""
        env = create_test_environment(owner=self.grp1)
        sub = Subscription.objects.create(
            user_profile=self.user1.results_profile, environment=env,
            email_success=False)

        with self.settings(API_BASE_URL=self.live_server_url):
            response = self.client.post(reverse('login'),
                dict(username=self.user1.username, password='AbCdEfGh'), follow=True)
            self.assertTrue(response.context['user'].is_active)

            response = self.client.get(reverse('preferences'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['env_sub_pairs'][0]['environment']['id'], env.id)
        self.assertEqual(response.context['env_sub_pairs'][0]['subscription']['id'], sub.id)

    def test_env_with_no_subscription(self):
        """Test the template and permissions between subscriptions."""
        # create user3 with access to env
        user = User.objects.create_user('joevendor3',
                                        'joe3@example.com', 'AbCdEfGh3')
        user.groups.add(self.grp1)
        env = create_test_environment(owner=self.grp1)
        # create sub with user3
        Subscription.objects.create(
            user_profile=user.results_profile, environment=env,
            email_success=False)

        # but login with user1, who has access to env
        with self.settings(API_BASE_URL=self.live_server_url):
            response = self.client.post(reverse('login'),
                dict(username=self.user1.username, password='AbCdEfGh'), follow=True)
            self.assertTrue(response.context['user'].is_active)

            response = self.client.get(reverse('preferences'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['env_sub_pairs'][0]['environment']['id'], env.id)
        self.assertEqual(response.context['env_sub_pairs'][0]['subscription'], None)
