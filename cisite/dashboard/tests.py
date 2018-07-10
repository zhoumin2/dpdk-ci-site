"""Define tests for dashboard app."""

from datetime import datetime
import pytz

from django.contrib.auth.models import User, Group
from django.contrib.contenttypes.models import ContentType
from django.http import Http404
from django.test import LiveServerTestCase, TestCase
from django.urls import reverse
from results.tests import create_test_environment
from results.models import Patch, PatchSet, Measurement, Parameter, \
    Subscription, Tarball, TestResult, TestRun
from .views import paginate_rest, parse_page

# TODO(DPDKLAB-301): Add unit tests for dashboard views


class DetailViewTests(LiveServerTestCase):
    """Test the detail view."""

    def setUp(self):
        super().setUp()
        grp = Group.objects.create(name='acme')
        user = User.objects.create_user(username='acmevendor', first_name='John',
                                   last_name='Vendor',
                                   email='jvendor@example.com',
                                   password='P@$$w0rd')
        user.groups.add(grp)
        self.env = create_test_environment(owner=grp)
        self.m1 = Measurement.objects.create(name='throughput', unit='Mpps',
                                             higher_is_better=True,
                                             environment=self.env)
        Parameter.objects.create(name='frame_size', unit='bytes', value=64,
                                 measurement=self.m1)
        Parameter.objects.create(name='txd/rxd', unit='bytes', value=64,
                                 measurement=self.m1)
        self.m2 = Measurement.objects.create(name='throughput', unit='Mpps',
                                             higher_is_better=True,
                                             environment=self.env)
        Parameter.objects.create(name='frame_size', unit='bytes', value=64,
                                 measurement=self.m2)
        Parameter.objects.create(name='txd/rxd', unit='bytes', value=512,
                                 measurement=self.m2)

    def tearDown(self):
        """Clear cache to fix an IntegrityError bug."""
        ContentType.objects.clear_cache()
        super().tearDown()

    def make_test_patchset(self):
        ps = PatchSet.objects.create(message_uid='20180601110742.11927',
                                     patch_count=1)
        Patch.objects.create(
            patchworks_id=40574,
            message_id='20180601110742.11927-1-thomas@monjalon.net',
            submitter='Thomas Monjalon <thomas@monjalon.net>',
            subject='version: 18.08-rc0', patchset=ps, version='v0',
            patch_number=1, date='2018-06-01 11:07:42+00:00',
            contacts='[{"display_name": "", "email": "dev@dpdk.org", '
                     '"how": "to"}]')
        tb = Tarball.objects.create(
            branch='dpdk', build_id=914, job_name='Apply-One-Patch-Set',
            commit_id='c6266cd55c3ab3bd13711ac0ae599fcf4a32ce84',
            patchset=ps)

        run = TestRun.objects.create(
            timestamp=datetime(2018, 6, 1, 20, 27, 42, tzinfo=pytz.utc),
            log_output_file='https://dpdklab.iol.unh.edu/jenkins/job/'
                            'ACME1-Performance-Test/3/artifact/gamma.zip',
            tarball=tb, environment=self.env)
        TestResult.objects.create(result='PASS', difference=-0.185655863091204,
                                  measurement=self.m1, run=run)
        TestResult.objects.create(result='PASS', difference=-0.664055231513893,
                                  measurement=self.m2, run=run)

        return ps

    def test_anon_load(self):
        """Test that the anonymous page loads."""
        ps = self.make_test_patchset()
        with self.settings(API_BASE_URL=self.live_server_url):
            response = self.client.get(reverse('dashboard-detail',
                                               args=[ps.id]))
            self.assertEqual(response.status_code, 200)

    def test_auth_load(self):
        """Test that the authenticated page loads."""
        ps = self.make_test_patchset()
        with self.settings(API_BASE_URL=self.live_server_url):
            # Log in
            response = self.client.post(reverse('login'),
                dict(username='acmevendor', password='P@$$w0rd'), follow=True)
            self.assertTrue(response.context['user'].is_active)

            response = self.client.get(reverse('dashboard-detail',
                                               args=[ps.id]),
                                       follow=True)
            self.assertEqual(response.status_code, 200)


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


class PaginationTests(TestCase):
    """Test the pagination.

    These are somewhat minimal since we are utiling the Django REST methods.
    """

    def test_valid_case(self):
        """Test that nothing breaks under normal circumstances."""
        context = {}
        paginate_rest(parse_page(5), context, 20)
        self.assertEqual(context['next'], '?page=6')
        self.assertEqual(context['previous'], '?page=4')

        context = {}
        paginate_rest(parse_page(10), context, 20)
        self.assertIsNone(context['next'])
        self.assertEqual(context['previous'], '?page=9')

        context = {}
        paginate_rest(parse_page(1), context, 20)
        self.assertEqual(context['next'], '?page=2')
        self.assertIsNone(context['previous'])

        context = {}
        paginate_rest(parse_page(1), context, 2)
        self.assertIsNone(context['next'])
        self.assertIsNone(context['previous'])

        # check ceil properly
        context = {}
        paginate_rest(parse_page(1), context, 3)
        self.assertEqual(context['next'], '?page=2')
        self.assertIsNone(context['previous'])

    def test_zero_index(self):
        """Test that zero gets converted to page 1."""
        context = {}
        paginate_rest(parse_page(0), context, 20)
        self.assertEqual(context['next'], '?page=2')

        context = {}
        paginate_rest(parse_page(0), context, 2)
        self.assertIsNone(context['next'])
        self.assertIsNone(context['previous'])

    def test_negatives(self):
        """Test that wrapping occurs."""
        context = {}
        paginate_rest(parse_page(-1), context, 20)
        self.assertEqual(context['previous'], '?page=9')

        context = {}
        paginate_rest(parse_page(-11), context, 20)
        self.assertEqual(context['previous'], '?page=9')

        context = {}
        paginate_rest(parse_page(-1), context, 2)
        self.assertIsNone(context['next'])
        self.assertIsNone(context['previous'])

        context = {}
        paginate_rest(parse_page(-11), context, 2)
        self.assertIsNone(context['next'])
        self.assertIsNone(context['previous'])

    def test_pages_greater_than_page(self):
        """Test that we get a 404 if page > pages."""
        with self.assertRaises(Http404):
            paginate_rest(parse_page(11), {}, 20)

        with self.assertRaises(Http404):
            paginate_rest(parse_page(2), {}, 2)
