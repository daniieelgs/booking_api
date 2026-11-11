"""F-017: a worker that belongs to no work group (so to no local) must not make the API answer 500."""
import datetime
import json

from flask_testing import TestCase

from app import create_app, db
from models.worker import WorkerModel
from tests.config_test import config_test, getUrl
from tests.configure_local_base import configure

WORKER_EMAIL = 'orphan@worker.com'
WORKER_PASSWORD = 'orphan-pw-123'


class TestWorkerWithoutWorkGroups(TestCase):

    def create_app(self):
        app = create_app(config_test)
        self.locals = []
        return app

    def setUp(self):
        db.create_all()
        config_test.config(db=db)
        self.a = configure(self.client, config_test.ADMIN_TOKEN, self.assertEqual, -1)
        self.locals = list(self.a.locals)
        self.headers = {'Authorization': f'Bearer {self.a.refresh_token}'}
        self.fresh = {'Authorization': f'Bearer {self.a.access_token}'}
        self.worker_id = self.create_orphan_worker()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        config_test.drop(self.locals)

    def create_orphan_worker(self):
        body = {'name': 'Orphan', 'last_name': 'Worker', 'email': WORKER_EMAIL, 'password': WORKER_PASSWORD,
                'work_groups': [self.a.work_groups[0]['id']]}
        r = self.client.post(getUrl('worker'), headers=self.headers, data=json.dumps(body), content_type='application/json')
        self.assertEqual(r.status_code, 201, r.json)
        worker_id = r.json['id']
        worker = WorkerModel.query.get(worker_id)
        worker.work_groups = []  # e.g. every group the worker was in has been removed
        db.session.commit()
        self.assertIsNone(WorkerModel.query.get(worker_id).local_id)
        return worker_id

    def call(self, method, url, headers, body=None):
        return getattr(self.client, method)(url, headers=headers, data=json.dumps(body if body is not None else {}),
                                            content_type='application/json')

    def test_local_id_is_none_without_work_groups_and_the_local_with_them(self):
        self.assertIsNone(WorkerModel.query.get(self.worker_id).local_id)
        with_groups = WorkerModel.query.get(self.a.workers[0]['id'])

        self.assertEqual(with_groups.local_id, self.a.local['id'])

    def test_private_views_answer_404(self):
        self.assertEqual(self.call('get', getUrl('worker', 'private', self.worker_id), self.headers).status_code, 404)
        self.assertEqual(self.call('get', getUrl('worker', 'private', self.worker_id, 'work_group'), self.headers).status_code, 404)

    def test_update_answers_404(self):
        body = {'name': 'Renamed', 'last_name': 'x', 'work_groups': [self.a.work_groups[0]['id']]}

        self.assertEqual(self.call('put', getUrl('worker', self.worker_id), self.headers, body).status_code, 404)

    def test_delete_answers_404(self):
        self.assertEqual(self.call('delete', getUrl('worker', self.worker_id), self.fresh).status_code, 404)

    def test_login_with_that_worker_is_refused_with_401(self):
        r = self.call('post', getUrl('local', 'login'), {}, {'email': WORKER_EMAIL, 'password': WORKER_PASSWORD})

        self.assertEqual(r.status_code, 401)

    def test_a_booking_cannot_be_assigned_to_that_worker(self):
        day = (datetime.datetime.now() + datetime.timedelta(days=1)).strftime('%Y-%m-%d')
        data = {'client_name': 'Client Test', 'client_tlf': '123456789', 'client_email': 'client@example.com',
                'datetime_init': f"{day} {self.a.timetable[0]['opening_time']}",
                'services_ids': [self.a.services[0]['id']], 'worker_id': self.worker_id}

        r = self.client.post(getUrl('booking', 'local', self.a.local['id']), data=json.dumps(data), content_type='application/json')

        self.assertEqual(r.status_code, 404, r.json)
