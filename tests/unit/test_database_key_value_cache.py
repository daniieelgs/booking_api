"""F-014: the in-memory cache used in Redis test mode needs the `time` module."""
import unittest
from unittest import mock

from helpers import Database


class TestKeyValueCacheTestMode(unittest.TestCase):

    def setUp(self):
        patcher = mock.patch.object(Database, 'is_redis_test_mode', return_value=True)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(Database.cache_memory.clear)
        self.addCleanup(Database.cache_expiry_time.clear)

    def test_register_and_get_roundtrip(self):
        Database.register_key_value_cache('k', 'v', exp=60)

        self.assertEqual(Database.get_key_value_cache('k'), 'v')

    def test_expired_key_is_dropped(self):
        Database.register_key_value_cache('k', 'v', exp=-1)

        self.assertIsNone(Database.get_key_value_cache('k'))
