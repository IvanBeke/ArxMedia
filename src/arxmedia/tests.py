from django.db import connection
from django.test import TestCase


class DatabaseSettingsTests(TestCase):
    def test_atomic_requests_enabled(self):
        self.assertIs(connection.settings_dict['ATOMIC_REQUESTS'], True)
