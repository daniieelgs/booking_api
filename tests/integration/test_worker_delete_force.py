"""F-018: deleting a worker with force=true reassigns (or cancels) its bookings; it must never hand one to the worker
that is being deleted. The loop used to overwrite the route's `worker_id`."""
import datetime
import json
from unittest import mock

from flask_testing import TestCase

from app import create_app, db
from models.booking import BookingModel
from tests.config_test import config_test, getUrl
from tests.configure_local_base import configure


class TestWorkerDeleteForce(TestCase):

    def create_app(self):
        app = create_app(config_test)
        self.locals = []
        return app

    def setUp(self):
        db.create_all()
        config_test.config(db=db)
        self.a = configure(self.client, config_test.ADMIN_TOKEN, self.assertEqual, -1)
        self.locals = list(self.a.locals)
        self.fresh = {'Authorization': f'Bearer {self.a.access_token}'}
        self.deleted, self.other1, self.other2 = (w['id'] for w in self.a.workers)
        self.day = (datetime.datetime.now() + datetime.timedelta(days=1)).strftime('%Y-%m-%d')
        # a deterministic candidate order: [first, second] instead of a random shuffle
        patcher = mock.patch('helpers.BookingController.random.shuffle', lambda items: None)
        patcher.start()
        self.addCleanup(patcher.stop)

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        config_test.drop(self.locals)

    def book(self, worker_id, hour):
        data = {'client_name': 'Client Test', 'client_tlf': '123456789', 'client_email': 'client@example.com',
                'datetime_init': f'{self.day} {hour}:00:00', 'services_ids': [self.a.services[0]['id']],
                'worker_id': worker_id}
        r = self.client.post(getUrl('booking', 'local', self.a.local['id']), data=json.dumps(data), content_type='application/json')
        self.assertEqual(r.status_code, 201, r.json)
        return r.json['booking']['id']

    def delete_worker_forced(self):
        r = self.client.delete(getUrl('worker', self.deleted) + '?force=true', headers=self.fresh, content_type='application/json')
        self.assertEqual(r.status_code, 204)

    def booking(self, booking_id):
        db.session.expire_all()
        return BookingModel.query.get(booking_id)

    def test_every_booking_is_reassigned_to_another_worker_never_to_the_deleted_one(self):
        first, second = self.book(self.deleted, '10'), self.book(self.deleted, '12')

        self.delete_worker_forced()

        for booking_id in (first, second):
            self.assertNotEqual(self.booking(booking_id).worker_id, self.deleted)
            self.assertIn(self.booking(booking_id).worker_id, (self.other1, self.other2))
            self.assertEqual(self.booking(booking_id).status.status, 'C')

    def test_after_a_cancelled_booking_the_next_one_is_still_not_given_to_the_deleted_worker(self):
        cancelled = self.book(self.deleted, '10')
        self.book(self.other1, '10')
        self.book(self.other2, '10')  # nobody is free at 10:00, so the first booking can only be cancelled
        reassigned = self.book(self.deleted, '12')

        self.delete_worker_forced()

        self.assertEqual(self.booking(cancelled).status.status, 'X')
        self.assertIn(self.booking(reassigned).worker_id, (self.other1, self.other2))
        self.assertEqual(self.booking(reassigned).status.status, 'C')
