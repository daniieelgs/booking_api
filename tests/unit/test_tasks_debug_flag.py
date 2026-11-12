"""F-013: celery_app.tasks must use the app's DEBUG flag, not logging.DEBUG (always 10)."""
import logging
import unittest

import globals as app_globals
from celery_app import tasks


class TestTasksDebugFlag(unittest.TestCase):

    def test_debug_is_the_application_flag_not_the_logging_level(self):
        self.assertIsNot(tasks.DEBUG, logging.DEBUG)
        self.assertEqual(tasks.DEBUG, app_globals.DEBUG)
