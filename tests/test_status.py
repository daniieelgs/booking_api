from flask_testing import TestCase

from app import create_app, db
from globals import API_VERSION
from tests import config_test


class TestStatus(TestCase):
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

    def test_health(self):
        response = self.client.get('/health')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {'status': 'ok'})

    def test_version(self):
        response = self.client.get('/version')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {'version': API_VERSION})

    def test_health_does_not_require_authentication(self):
        response = self.client.get('/health')
        self.assertNotEqual(response.status_code, 401)
