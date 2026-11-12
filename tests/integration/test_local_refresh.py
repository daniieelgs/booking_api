"""POST /local/refresh renews the refresh token: the current one expires and a new one is returned (no access token)."""
import json

from flask_testing import TestCase

from app import create_app, db
from tests.config_test import config_test, getUrl


class TestLocalRefresh(TestCase):

    def create_app(self):
        app = create_app(config_test)
        self.locals = []
        return app

    def setUp(self):
        db.create_all()
        config_test.config(db=db)
        self.data = {'name': 'Local-Test', 'tlf': '123456789', 'email': 'refresh@test.com', 'address': 'Test Address',
                     'postal_code': '98765', 'village': 'Test Village', 'province': 'Test Province',
                     'location': 'Europe/Madrid', 'password': 'Refresh-pass-1234'}
        r = self.client.post(getUrl('local'), data=json.dumps(self.data), headers=self.bearer(config_test.ADMIN_TOKEN),
                             content_type='application/json')
        self.assertEqual(r.status_code, 201)
        self.locals = [r.json['local']['id']]
        self.refresh_token = r.json['refresh_token']
        self.access_token = r.json['access_token']

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        config_test.drop(self.locals)

    def bearer(self, token):
        return {'Authorization': f'Bearer {token}'}

    def refresh(self, token):
        return self.client.post(getUrl('local', 'refresh'), headers=self.bearer(token), content_type='application/json')

    def whoami(self, token):
        return self.client.get(getUrl('local'), headers=self.bearer(token))

    def login(self):
        r = self.client.post(getUrl('local', 'login'), data=json.dumps({'email': self.data['email'], 'password': self.data['password']}),
                             content_type='application/json')
        self.assertEqual(r.status_code, 200)
        return r.json['refresh_token']

    def test_returns_a_new_refresh_token_and_no_access_token(self):
        r = self.refresh(self.refresh_token)

        self.assertEqual(r.status_code, 200)
        self.assertNotEqual(r.json['refresh_token'], self.refresh_token)
        self.assertNotIn('access_token', r.json)

    def test_the_new_token_works(self):
        new_token = self.refresh(self.refresh_token).json['refresh_token']

        self.assertEqual(self.whoami(new_token).status_code, 200)

    def test_the_old_refresh_token_is_no_longer_valid(self):
        old_token = self.refresh_token
        self.refresh(old_token)

        self.assertEqual(self.whoami(old_token).status_code, 401)
        self.assertEqual(self.refresh(old_token).status_code, 401)

    def test_refreshing_twice_in_a_row_with_the_new_token_keeps_working(self):
        first = self.refresh(self.refresh_token).json['refresh_token']
        second = self.refresh(first)

        self.assertEqual(second.status_code, 200)
        self.assertEqual(self.refresh(first).status_code, 401)

    def test_other_sessions_of_the_same_local_are_not_affected(self):
        other_session = self.login()

        self.refresh(self.refresh_token)

        self.assertEqual(self.whoami(other_session).status_code, 200)

    def test_requires_a_refresh_token(self):
        self.assertEqual(self.client.post(getUrl('local', 'refresh'), content_type='application/json').status_code, 401)
        self.assertIn(self.refresh(self.access_token).status_code, (401, 422))
