"""A local must never read or change the data of another local through the id-based endpoints.

Local A owns everything (work groups, services, workers, a booking); local B is a second, empty local that tries
to reach it with its own valid tokens. Each case expects a refusal (401/403/404) and checks that A's data is intact.
"""
import datetime
import json

from flask_testing import TestCase

from app import create_app, db
from globals import WORKER_ROLE
from helpers.security import generateTokens
from models.user_session import UserSessionModel
from tests.config_test import config_test, getUrl
from tests.configure_local_base import configure

REFUSED = (401, 403, 404)


class TestCrossLocalOwnership(TestCase):

    def create_app(self):
        app = create_app(config_test)
        self.locals = []
        return app

    def setUp(self):
        db.create_all()
        config_test.config(db=db)
        self.a = configure(self.client, config_test.ADMIN_TOKEN, self.assertEqual, -1)
        self.locals = list(self.a.locals)
        self.b = self.create_other_local()
        self.b_work_group = self.create_work_group_for_b()
        self.booking_id = self.create_booking()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        config_test.drop(self.locals)

    def create_other_local(self):
        data = {
            'name': 'Other-Local', 'tlf': '987654321', 'email': 'other@test.com', 'address': 'Other Address',
            'postal_code': '11111', 'village': 'Other Village', 'province': 'Other Province', 'location': 'Europe/Madrid',
        }
        r = self.client.post(getUrl('local'), data=json.dumps(data),
                             headers={'Authorization': f'Bearer {config_test.ADMIN_TOKEN}'}, content_type='application/json')
        self.assertEqual(r.status_code, 201)
        self.locals.append(r.json['local']['id'])
        return r.json

    def create_work_group_for_b(self):
        # B's own work group, so that PUT bodies are valid for B and only the ownership check can refuse them
        r = self.client.post(getUrl('work_group'), headers=self.refresh(self.b),
                             data=json.dumps({'name': 'B work group', 'description': 'B'}), content_type='application/json')
        self.assertEqual(r.status_code, 201, r.json)
        return r.json['id']

    def create_booking(self):
        day = (datetime.datetime.now() + datetime.timedelta(days=1)).strftime('%Y-%m-%d')
        data = {'client_name': 'Client Test', 'client_tlf': '123456789', 'client_email': 'client@example.com',
                'datetime_init': f"{day} {self.a.timetable[0]['opening_time']}",
                'services_ids': [self.a.services[0]['id']]}
        r = self.client.post(getUrl('booking', 'local', self.a.local['id']), data=json.dumps(data),
                             content_type='application/json')
        self.assertEqual(r.status_code, 201)
        return r.json['booking']['id']

    @staticmethod
    def token(who, kind):
        key = f'{kind}_token'
        return f"Bearer {who[key] if isinstance(who, dict) else getattr(who, key)}"

    def refresh(self, who):
        return {'Authorization': self.token(who, 'refresh')}

    def access(self, who):
        return {'Authorization': self.token(who, 'access')}

    def call(self, method, url, headers, body=None):
        return getattr(self.client, method)(url, headers=headers, data=json.dumps(body if body is not None else {}),
                                            content_type='application/json')

    def assertRefused(self, response):
        self.assertIn(response.status_code, REFUSED, response.json)

    def assertForbidden(self, response):
        # authenticated but not allowed: 403 (401 is reserved for missing or invalid credentials)
        self.assertEqual(response.status_code, 403, response.json)

    # --- services ---

    def test_other_local_cannot_update_a_service(self):
        service = dict(self.a.services[0], name='hijacked', work_group=self.b_work_group)
        body = {k: service[k] for k in ('name', 'description', 'duration', 'price', 'work_group')}

        self.assertRefused(self.call('put', getUrl('service', service['id']), self.refresh(self.b), body))

        self.assertNotEqual(self.client.get(getUrl('service', service['id'])).json['name'], 'hijacked')

    def test_other_local_cannot_delete_a_service(self):
        service_id = self.a.services[0]['id']

        self.assertRefused(self.call('delete', getUrl('service', service_id), self.access(self.b)))

        self.assertEqual(self.client.get(getUrl('service', service_id)).status_code, 200)

    def test_other_local_cannot_create_a_service_in_a_foreign_work_group(self):
        body = {'name': 'Service X', 'description': 'x', 'duration': 30, 'price': 1, 'work_group': self.a.work_groups[0]['id']}

        self.assertRefused(self.call('post', getUrl('service'), self.refresh(self.b), body))

    # --- work groups ---

    def test_other_local_cannot_update_a_work_group(self):
        wg = self.a.work_groups[0]

        self.assertRefused(self.call('put', getUrl('work_group', wg['id']), self.refresh(self.b),
                                     {'name': 'hijacked', 'description': 'x'}))

        self.assertNotEqual(self.client.get(getUrl('work_group', wg['id'])).json['name'], 'hijacked')

    def test_other_local_cannot_delete_a_work_group(self):
        wg_id = self.a.work_groups[1]['id']

        self.assertRefused(self.call('delete', getUrl('work_group', wg_id), self.access(self.b)))

        self.assertEqual(self.client.get(getUrl('work_group', wg_id)).status_code, 200)

    def test_other_local_cannot_read_the_private_view_of_a_work_group(self):
        url = getUrl('work_group', 'private', self.a.work_groups[0]['id'], 'workers')

        self.assertRefused(self.call('get', url, self.refresh(self.b)))

    # --- workers ---

    def test_other_local_cannot_read_a_worker_privately(self):
        worker_id = self.a.workers[0]['id']

        self.assertRefused(self.call('get', getUrl('worker', 'private', worker_id), self.refresh(self.b)))
        self.assertRefused(self.call('get', getUrl('worker', 'private', worker_id, 'work_group'), self.refresh(self.b)))

    def test_other_local_cannot_update_a_worker(self):
        worker = self.a.workers[0]
        body = {'name': 'hijacked', 'last_name': 'x', 'work_groups': [self.b_work_group]}

        self.assertRefused(self.call('put', getUrl('worker', worker['id']), self.refresh(self.b), body))

        self.assertNotEqual(self.client.get(getUrl('worker', worker['id'])).json['name'], 'hijacked')

    def test_other_local_cannot_delete_a_worker(self):
        worker_id = self.a.workers[2]['id']

        self.assertRefused(self.call('delete', getUrl('worker', worker_id), self.access(self.b)))

        self.assertEqual(self.client.get(getUrl('worker', worker_id)).status_code, 200)

    def test_other_local_cannot_create_a_worker_in_a_foreign_work_group(self):
        body = {'name': 'Worker X', 'last_name': 'Surname', 'work_groups': [self.a.work_groups[0]['id']]}

        self.assertRefused(self.call('post', getUrl('worker'), self.refresh(self.b), body))

    # --- bookings ---

    def booking_as_owner(self):
        return self.call('get', getUrl('booking', self.booking_id), self.refresh(self.a))

    def test_other_local_cannot_read_a_booking(self):
        self.assertForbidden(self.call('get', getUrl('booking', self.booking_id), self.refresh(self.b)))

    def test_other_local_cannot_delete_a_booking(self):
        self.assertForbidden(self.call('delete', getUrl('booking', self.booking_id), self.refresh(self.b)))

        self.assertEqual(self.booking_as_owner().status_code, 200)

    def test_other_local_cannot_patch_a_booking(self):
        self.assertForbidden(self.call('patch', getUrl('booking', self.booking_id), self.refresh(self.b), {'client_name': 'Hijacked'}))

        self.assertEqual(self.booking_as_owner().json['client_name'], 'Client Test')

    def test_other_local_cannot_replace_a_booking(self):
        day = (datetime.datetime.now() + datetime.timedelta(days=2)).strftime('%Y-%m-%d')
        body = {'client_name': 'Hijacked', 'client_email': 'h@example.com', 'client_tlf': '123456789', 'new_status': 'C',
                'datetime_init': f'{day} 10:00:00', 'services_ids': [self.a.services[0]['id']]}

        self.assertForbidden(self.call('put', getUrl('booking', self.booking_id), self.refresh(self.b), body))

        self.assertEqual(self.booking_as_owner().json['client_name'], 'Client Test')

    def test_other_local_cannot_confirm_a_booking(self):
        self.assertForbidden(self.call('get', getUrl('booking', 'confirm', self.booking_id), self.refresh(self.b)))

    def test_other_local_cannot_cancel_a_booking(self):
        self.assertForbidden(self.call('delete', getUrl('booking', 'cancel', self.booking_id), self.refresh(self.b)))

        self.assertNotEqual(self.booking_as_owner().json['status']['status'], 'X')

    def test_a_booking_in_one_local_cannot_use_the_services_of_another(self):
        day = (datetime.datetime.now() + datetime.timedelta(days=1)).strftime('%Y-%m-%d')
        data = {'client_name': 'Client', 'client_tlf': '123456789', 'client_email': 'c@example.com',
                'datetime_init': f'{day} 10:00:00', 'services_ids': [self.a.services[0]['id']]}

        r = self.client.post(getUrl('booking', 'local', self.b['local']['id']), data=json.dumps(data),
                             content_type='application/json')

        self.assertIn(r.status_code, (400, 404, 409), r.json)

    # --- worker sessions: a worker only handles its own bookings ---

    def worker_headers(self, worker_id):
        db.session.add(UserSessionModel(user=WORKER_ROLE, name='Worker'))
        db.session.commit()
        token = generateTokens(self.a.local['id'], self.a.local['id'], access_token=False, refresh_token=True,
                               claims={}, user_role=WORKER_ROLE, user_id=worker_id)
        return {'Authorization': f'Bearer {token}'}

    def other_worker_id(self):
        owner = self.call('get', getUrl('booking', self.booking_id), self.refresh(self.a)).json
        return next(w['id'] for w in self.a.workers if w['id'] != owner['worker']['id'])

    def test_a_worker_cannot_cancel_a_booking_of_another_worker(self):
        headers = self.worker_headers(self.other_worker_id())

        self.assertForbidden(self.call('delete', getUrl('booking', 'cancel', self.booking_id), headers))

    def test_a_worker_cannot_confirm_a_booking_of_another_worker(self):
        headers = self.worker_headers(self.other_worker_id())

        self.assertForbidden(self.call('get', getUrl('booking', 'confirm', self.booking_id), headers))

    def test_a_worker_cannot_delete_a_booking(self):
        headers = self.worker_headers(self.other_worker_id())

        self.assertForbidden(self.call('delete', getUrl('booking', self.booking_id), headers))
