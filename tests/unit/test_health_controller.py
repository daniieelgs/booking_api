import unittest
from unittest import mock

from helpers import HealthController
from helpers.HealthController import compute_status


class TestComputeStatus(unittest.TestCase):

    def test_ok_only_when_everything_works(self):
        self.assertEqual(compute_status(True, True, True), 'ok')

    def test_each_failure_maps_to_its_status(self):
        self.assertEqual(compute_status(True, True, False), 'degraded')
        self.assertEqual(compute_status(True, False, True), 'error')
        self.assertEqual(compute_status(False, True, True), 'critical')

    def test_worst_failure_wins(self):
        self.assertEqual(compute_status(True, False, False), 'error')
        self.assertEqual(compute_status(False, False, False), 'critical')
        self.assertEqual(compute_status(False, True, False), 'critical')


class TestWorkerCheck(unittest.TestCase):

    def setUp(self):
        HealthController._worker_cache.update(at=0.0, value=None)
        self.addCleanup(HealthController._worker_cache.update, at=0.0, value=None)
        patcher = mock.patch.object(HealthController, 'is_redis_test_mode', return_value=False)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.celery = mock.Mock()
        app = mock.Mock(extensions={'celery': self.celery})
        patcher = mock.patch.object(HealthController, 'current_app', app)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_true_when_a_worker_answers(self):
        self.celery.control.ping.return_value = [{'celery@w1': {'ok': 'pong'}}]

        self.assertTrue(HealthController._ping_worker())

    def test_false_when_nobody_answers(self):
        self.celery.control.ping.return_value = []

        self.assertFalse(HealthController._ping_worker())

    def test_false_when_the_broker_raises(self):
        self.celery.control.ping.side_effect = ConnectionError('broker down')

        self.assertFalse(HealthController._ping_worker())

    def test_true_in_test_mode_without_touching_celery(self):
        with mock.patch.object(HealthController, 'is_redis_test_mode', return_value=True):
            self.assertTrue(HealthController._ping_worker())

        self.celery.control.ping.assert_not_called()

    def test_stops_at_the_first_reply(self):
        self.celery.control.ping.return_value = [{'w': {'ok': 'pong'}}]

        HealthController._ping_worker()

        self.assertEqual(self.celery.control.ping.call_args.kwargs['limit'], 1)

    def test_result_is_cached_for_a_short_time(self):
        self.celery.control.ping.return_value = []
        with mock.patch.object(HealthController, 'HEALTH_CACHE_SECONDS', 10):
            self.assertFalse(HealthController.check_worker())
            self.assertFalse(HealthController.check_worker())

        self.assertEqual(self.celery.control.ping.call_count, 1)

    def test_cache_expires(self):
        self.celery.control.ping.return_value = []
        with mock.patch.object(HealthController, 'HEALTH_CACHE_SECONDS', 0):
            HealthController.check_worker()
            self.celery.control.ping.return_value = [{'w': {'ok': 'pong'}}]
            self.assertTrue(HealthController.check_worker())


if __name__ == '__main__':
    unittest.main()
