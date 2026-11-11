from flask_testing import TestCase

from app import create_app, db
from tests.config_test import config_test


class TestCeleryConfig(TestCase):
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

    def test_tasks_are_acknowledged_when_they_finish_so_a_dead_worker_does_not_lose_an_email(self):
        celery = self.app.extensions['celery']

        self.assertTrue(celery.conf.task_acks_late)
