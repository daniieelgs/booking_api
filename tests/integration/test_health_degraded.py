from unittest import mock

from flask_testing import TestCase

from app import create_app, db
from helpers import HealthController
from tests.config_test import config_test


class TestHealthDegraded(TestCase):
    def create_app(self):
        app = create_app(config_test)
        self.locals = []
        return app

    def setUp(self):
        db.create_all()
        config_test.config(db=db)

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        config_test.drop(self.locals)

    def get_health(self, database=True, redis=True, worker=True):
        with mock.patch('helpers.HealthController.check_database', return_value=database),                 mock.patch('helpers.HealthController.check_redis', return_value=redis),                 mock.patch('helpers.HealthController.check_worker', return_value=worker):
            return self.client.get('/health')

    def test_ok_when_everything_works(self):
        response = self.get_health()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {'status': 'ok'})

    def test_degraded_when_only_the_worker_is_down(self):
        self.assertEqual(self.get_health(worker=False).json, {'status': 'degraded'})

    def test_error_when_redis_is_down(self):
        self.assertEqual(self.get_health(redis=False).json, {'status': 'error'})

    def test_critical_when_the_database_is_down(self):
        self.assertEqual(self.get_health(database=False).json, {'status': 'critical'})

    def test_never_returns_server_error_whatever_fails(self):
        self.assertEqual(self.get_health(False, False, False).status_code, 200)

    def test_does_not_require_authentication(self):
        self.assertNotIn(self.get_health(False, False, False).status_code, (401, 403))

    def test_worker_is_not_pinged_when_redis_is_down(self):
        with mock.patch('helpers.HealthController.check_database', return_value=True),                 mock.patch('helpers.HealthController.check_redis', return_value=False),                 mock.patch('helpers.HealthController.check_worker') as worker:
            self.client.get('/health')

        worker.assert_not_called()

    def test_health_reflects_recovery(self):
        self.assertEqual(self.get_health(redis=False).json['status'], 'error')
        self.assertEqual(self.get_health().json['status'], 'ok')

    def test_real_database_check_passes_against_the_test_database(self):
        self.assertTrue(HealthController.check_database())

    def test_real_database_check_fails_when_the_session_raises(self):
        with mock.patch.object(HealthController.db.session, 'execute', side_effect=OSError('db gone')):
            self.assertFalse(HealthController.check_database())
