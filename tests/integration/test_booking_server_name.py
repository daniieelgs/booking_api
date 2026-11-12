import datetime
import json
from unittest import mock

from flask_testing import TestCase

import globals as app_globals
from app import create_app, db
from tests.config_test import config_test, getUrl, setParams
from tests.configure_local_base import configure

ENDPOINT = 'booking'
SENTINEL = 'sentinel-server'


class TestBookingServerName(TestCase):
    def create_app(self):
        app = create_app(config_test)
        self.locals = []
        return app

    def setUp(self):
        db.create_all()
        config_test.config(db=db)
        self.admin_token = config_test.ADMIN_TOKEN
        self.local = configure(self.client, self.admin_token, self.assertEqual, -1)
        self.locals = self.local.locals

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        config_test.drop(self.locals)

    def booking_data(self):
        opening = self.local.timetable[0]['opening_time']
        day = (datetime.datetime.now() + datetime.timedelta(days=1)).strftime('%Y-%m-%d')
        return {
            'client_name': 'Client Test',
            'client_tlf': '123456789',
            'client_email': 'client@example.com',
            'datetime_init': f'{day} {opening}',
            'services_ids': [self.local.services[0]['id']],
        }

    def create_public_booking(self):
        r = self.client.post(getUrl(ENDPOINT, 'local', self.local.local['id']), data=json.dumps(self.booking_data()), content_type='application/json')
        self.assertEqual(r.status_code, 201)
        return r.json

    def create_admin_booking(self):
        data = self.booking_data()
        data['worker_id'] = self.local.workers[0]['id']
        r = self.client.post(getUrl(ENDPOINT, 'admin'), data=json.dumps(data), headers={'Authorization': f'Bearer {self.admin_token}'}, content_type='application/json')
        self.assertEqual(r.status_code, 201)
        return r.json

    def get_booking_admin(self, booking_id):
        r = self.client.get(getUrl(ENDPOINT, booking_id), headers={'Authorization': f'Bearer {self.local.refresh_token}'}, content_type='application/json')
        self.assertEqual(r.status_code, 200)
        return r.json

    def test_public_booking_stores_configured_server_name(self):
        with mock.patch('helpers.BookingController.SERVER_NAME', SENTINEL):
            booking = self.create_public_booking()

        self.assertEqual(self.get_booking_admin(booking['booking']['id'])['server_name'], SENTINEL)

    def test_admin_booking_stores_configured_server_name(self):
        with mock.patch('resources.booking.SERVER_NAME', SENTINEL):
            booking = self.create_admin_booking()

        self.assertEqual(self.get_booking_admin(booking['booking']['id'])['server_name'], SENTINEL)

    def test_public_booking_defaults_to_global_server_name(self):
        booking = self.create_public_booking()

        self.assertEqual(self.get_booking_admin(booking['booking']['id'])['server_name'], app_globals.SERVER_NAME)

    def test_admin_booking_defaults_to_global_server_name(self):
        booking = self.create_admin_booking()

        self.assertEqual(self.get_booking_admin(booking['booking']['id'])['server_name'], app_globals.SERVER_NAME)

    def test_server_name_is_listed_in_bookings(self):
        with mock.patch('helpers.BookingController.SERVER_NAME', SENTINEL):
            booking_id = self.create_public_booking()['booking']['id']

        day = (datetime.datetime.now() + datetime.timedelta(days=1)).strftime('%Y-%m-%d')
        r = self.client.get(setParams(getUrl(ENDPOINT, 'all'), date=day), headers={'Authorization': f'Bearer {self.local.refresh_token}'}, content_type='application/json')

        self.assertEqual(r.status_code, 200)
        listed = [b for b in r.json['bookings'] if b['id'] == booking_id]
        self.assertEqual(len(listed), 1)
        self.assertEqual(listed[0]['server_name'], SENTINEL)

    def test_server_name_cannot_be_set_by_the_client(self):
        data = self.booking_data()
        data['server_name'] = 'forged'

        r = self.client.post(getUrl(ENDPOINT, 'local', self.local.local['id']), data=json.dumps(data), content_type='application/json')

        if r.status_code == 201:
            self.assertNotEqual(self.get_booking_admin(r.json['booking']['id'])['server_name'], 'forged')
        else:
            self.assertEqual(r.status_code, 422)

    def test_default_server_name_is_not_empty(self):
        self.assertTrue(app_globals.SERVER_NAME)
