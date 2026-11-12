import unittest
from unittest import mock

import redis

from helpers import Database

# Database.redis is the same module object as redis, so inside a patch of ConnectionPool the name resolves to the mock.
REAL_CONNECTION_POOL = redis.ConnectionPool


class RedisPoolTestCase(unittest.TestCase):

    def setUp(self):
        Database._redis_pool = None
        patcher = mock.patch.object(Database, 'is_redis_test_mode', return_value=False)
        self.test_mode = patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(setattr, Database, '_redis_pool', None)


class TestGetRedisPool(RedisPoolTestCase):

    def test_returns_none_in_test_mode(self):
        self.test_mode.return_value = True

        with mock.patch.object(Database.redis, 'ConnectionPool') as pool:
            self.assertIsNone(Database._get_redis_pool())

        pool.assert_not_called()

    def test_builds_pool_with_resilience_options(self):
        with mock.patch.object(Database.redis, 'ConnectionPool') as pool, \
                mock.patch.object(Database, 'REDIS_HOST', 'redis-host'), \
                mock.patch.object(Database, 'REDIS_PORT', '6380'), \
                mock.patch.object(Database, 'REDIS_PASSWORD', 'secret'):
            Database._get_redis_pool()

        kwargs = pool.call_args.kwargs
        self.assertEqual(kwargs['host'], 'redis-host')
        self.assertEqual(kwargs['port'], 6380)
        self.assertEqual(kwargs['password'], 'secret')
        self.assertTrue(kwargs['retry_on_timeout'])
        self.assertTrue(kwargs['socket_keepalive'])
        self.assertEqual(kwargs['health_check_interval'], 15)
        self.assertIn(redis.ConnectionError, kwargs['retry_on_error'])
        self.assertIn(redis.TimeoutError, kwargs['retry_on_error'])
        self.assertEqual(kwargs['retry']._retries, 3)

    def test_pool_is_created_once(self):
        with mock.patch.object(Database.redis, 'ConnectionPool') as pool:
            first = Database._get_redis_pool()
            second = Database._get_redis_pool()

        self.assertIs(first, second)
        pool.assert_called_once()


class TestCreateRedisConnection(RedisPoolTestCase):

    def test_returns_none_in_test_mode(self):
        self.test_mode.return_value = True

        self.assertIsNone(Database.create_redis_connection())

    def test_uses_shared_pool(self):
        with mock.patch.object(Database.redis, 'ConnectionPool') as pool, \
                mock.patch.object(Database.redis, 'Redis') as client:
            connection = Database.create_redis_connection()

        client.assert_called_once_with(connection_pool=pool.return_value)
        self.assertIs(connection, client.return_value)


class TestPingRedis(RedisPoolTestCase):

    def test_true_in_test_mode(self):
        self.test_mode.return_value = True

        self.assertTrue(Database.ping_redis())

    def test_true_when_ping_succeeds(self):
        connection = mock.Mock(ping=mock.Mock(return_value=True))

        with mock.patch.object(Database, 'create_redis_connection', return_value=connection):
            self.assertTrue(Database.ping_redis())

    def test_false_when_ping_raises(self):
        connection = mock.Mock(ping=mock.Mock(side_effect=redis.ConnectionError('down')))

        with mock.patch.object(Database, 'create_redis_connection', return_value=connection):
            self.assertFalse(Database.ping_redis())

    def test_false_when_connection_cannot_be_created(self):
        with mock.patch.object(Database, 'create_redis_connection', side_effect=OSError('boom')):
            self.assertFalse(Database.ping_redis())

    def test_false_when_connection_is_none(self):
        with mock.patch.object(Database, 'create_redis_connection', return_value=None):
            self.assertFalse(Database.ping_redis())

    def test_false_against_unreachable_server(self):
        # Real client, nothing listening: the failure must be a genuine ConnectionError that ping_redis swallows.
        def short_timeout_pool(**kwargs):
            return REAL_CONNECTION_POOL(host=kwargs['host'], port=kwargs['port'], socket_connect_timeout=0.2)

        with mock.patch.object(Database, 'REDIS_HOST', '127.0.0.1'), \
                mock.patch.object(Database, 'REDIS_PORT', '1'), \
                mock.patch.object(Database.redis, 'ConnectionPool', side_effect=short_timeout_pool):
            with self.assertRaises((redis.ConnectionError, redis.TimeoutError)):
                Database.create_redis_connection().ping()

            self.assertFalse(Database.ping_redis())


if __name__ == '__main__':
    unittest.main()
