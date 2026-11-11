import json
import unittest

from flask_testing import TestCase

from app import create_app, db
from db import addAndCommit
from globals import WORKER_ROLE
from helpers.security import generateTokens
from models.user_session import UserSessionModel
from tests.config_test import config_test, getUrl, setParams
from tests.configure_local_base import LocalBase

JAN_10 = ('2030-01-10T00:00:00', '2030-01-12T00:00:00')
JAN_20 = ('2030-01-20T00:00:00', '2030-01-22T00:00:00')


class TestClose(TestCase):

    def create_app(self):
        app = create_app(config_test)
        self.locals = []
        return app

    def setUp(self):
        db.create_all()
        config_test.config(db=db)
        self.admin_token = config_test.ADMIN_TOKEN
        base = LocalBase(self.client, self.admin_token, self.assertEqual)
        base.create_local(-1, set_local_settings=False, set_smtp_settings=False)
        self.locals.extend(base.locals)
        self.local = base

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        config_test.drop(self.locals)

    def bearer(self, token=None):
        return {'Authorization': f'Bearer {token or self.local.refresh_token}'}

    def body(self, period, description=None):
        data = {'datetime_init': period[0], 'datetime_end': period[1]}
        if description is not None:
            data['description'] = description
        return data

    def post_close(self, period, description=None, token=None, headers=True):
        return self.client.post(getUrl('close'), data=json.dumps(self.body(period, description)),
                                headers=self.bearer(token) if headers else {}, content_type='application/json')

    def put_close(self, close_id, period, description=None, token=None, headers=True):
        return self.client.put(getUrl('close', close_id), data=json.dumps(self.body(period, description)),
                               headers=self.bearer(token) if headers else {}, content_type='application/json')

    def delete_close(self, close_id, token=None, headers=True):
        return self.client.delete(getUrl('close', close_id), headers=self.bearer(token) if headers else {})

    def get_close(self, token=None, headers=True, **params):
        url = setParams(getUrl('close'), **params) if params else getUrl('close')
        return self.client.get(url, headers=self.bearer(token) if headers else {})

    def get_close_public(self, local_id, **params):
        url = getUrl('close', 'local', local_id)
        return self.client.get(setParams(url, **params) if params else url)

    def create_close(self, period=JAN_10, description='holidays'):
        r = self.post_close(period, description)
        self.assertEqual(r.status_code, 200)
        return r.json

    def create_other_local(self):
        data = {
            'name': 'Other-Local', 'tlf': '987654321', 'email': 'other@test.com', 'address': 'Other Address',
            'postal_code': '11111', 'village': 'Other Village', 'province': 'Other Province', 'location': 'Europe/Madrid',
        }
        r = self.client.post(getUrl('local'), data=json.dumps(data), headers=self.bearer(self.admin_token), content_type='application/json')
        self.assertEqual(r.status_code, 201)
        self.locals.append(r.json['local']['id'])
        return r.json

    def worker_token(self):
        db.session.add(UserSessionModel(user=WORKER_ROLE, name='Worker'))
        db.session.commit()
        return generateTokens(self.local.local['id'], self.local.local['id'], access_token=False, refresh_token=True,
                              claims={}, user_role=WORKER_ROLE, user_id=1)

    # --- POST /close ---

    def test_create_close_day_returns_it_with_an_id(self):
        r = self.post_close(JAN_10, 'holidays')

        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json['id'])
        self.assertEqual(r.json['datetime_init'], JAN_10[0])
        self.assertEqual(r.json['datetime_end'], JAN_10[1])
        self.assertEqual(r.json['description'], 'holidays')

    def test_create_close_day_description_is_optional(self):
        r = self.post_close(JAN_10)

        self.assertEqual(r.status_code, 200)

    def test_create_close_day_init_after_end_is_400(self):
        r = self.post_close((JAN_10[1], JAN_10[0]))

        self.assertEqual(r.status_code, 400)

    def test_create_close_day_init_equal_end_is_400(self):
        r = self.post_close((JAN_10[0], JAN_10[0]))

        self.assertEqual(r.status_code, 400)

    def test_create_close_day_overlapping_is_409(self):
        self.create_close(JAN_10)

        r = self.post_close(('2030-01-11T00:00:00', '2030-01-13T00:00:00'))

        self.assertEqual(r.status_code, 409)

    def test_create_close_day_contained_in_existing_is_409(self):
        self.create_close(JAN_10)

        r = self.post_close(('2030-01-10T06:00:00', '2030-01-11T00:00:00'))

        self.assertEqual(r.status_code, 409)

    def test_create_close_day_non_overlapping_is_allowed(self):
        self.create_close(JAN_10)

        r = self.post_close(JAN_20)

        self.assertEqual(r.status_code, 200)

    def test_create_close_day_missing_fields_is_422(self):
        r = self.client.post(getUrl('close'), data=json.dumps({'datetime_init': JAN_10[0]}), headers=self.bearer(), content_type='application/json')

        self.assertEqual(r.status_code, 422)

    def test_create_close_day_requires_authentication(self):
        r = self.post_close(JAN_10, headers=False)

        self.assertEqual(r.status_code, 401)

    def test_create_close_day_forbidden_for_worker_session(self):
        r = self.post_close(JAN_10, token=self.worker_token())

        self.assertEqual(r.status_code, 401)

    # --- GET /close ---

    def test_list_close_days_empty(self):
        r = self.get_close()

        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json, [])

    def test_list_close_days_returns_created_ones(self):
        first = self.create_close(JAN_10)
        second = self.create_close(JAN_20)

        r = self.get_close()

        self.assertEqual(r.status_code, 200)
        self.assertCountEqual([c['id'] for c in r.json], [first['id'], second['id']])

    def test_list_close_days_filters_by_datetime_init(self):
        self.create_close(JAN_10)
        later = self.create_close(JAN_20)

        r = self.get_close(datetime_init='2030-01-15T00:00:00')

        self.assertEqual([c['id'] for c in r.json], [later['id']])

    def test_list_close_days_filters_by_datetime_end(self):
        earlier = self.create_close(JAN_10)
        self.create_close(JAN_20)

        r = self.get_close(datetime_end='2030-01-15T00:00:00')

        self.assertEqual([c['id'] for c in r.json], [earlier['id']])

    def test_list_close_days_only_returns_own_local(self):
        self.create_close(JAN_10)
        other = self.create_other_local()

        r = self.get_close(token=other['refresh_token'])

        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json, [])

    def test_list_close_days_requires_authentication(self):
        r = self.get_close(headers=False)

        self.assertEqual(r.status_code, 401)

    def test_expired_close_days_are_purged_on_listing(self):
        past = self.client.post(getUrl('close'), data=json.dumps(self.body(('2000-01-01T00:00:00', '2000-01-02T00:00:00'))),
                               headers=self.bearer(), content_type='application/json')
        self.assertEqual(past.status_code, 200)

        r = self.get_close()

        self.assertEqual(r.json, [])

    # --- GET /close/local/<local_id> (public) ---

    def test_public_list_does_not_require_authentication(self):
        created = self.create_close(JAN_10)

        r = self.get_close_public(self.local.local['id'])

        self.assertEqual(r.status_code, 200)
        self.assertEqual([c['id'] for c in r.json], [created['id']])

    def test_public_list_filters_by_range(self):
        self.create_close(JAN_10)
        later = self.create_close(JAN_20)

        r = self.get_close_public(self.local.local['id'], datetime_init='2030-01-15T00:00:00')

        self.assertEqual([c['id'] for c in r.json], [later['id']])

    def test_public_list_unknown_local_is_404(self):
        r = self.get_close_public('does-not-exist')

        self.assertEqual(r.status_code, 404)

    # --- PUT /close/<id> ---

    def test_update_close_day(self):
        created = self.create_close(JAN_10, 'old')

        r = self.put_close(created['id'], JAN_20, 'new')

        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json['id'], created['id'])
        self.assertEqual(r.json['datetime_init'], JAN_20[0])
        self.assertEqual(r.json['description'], 'new')

    def test_update_close_day_can_overlap_itself(self):
        created = self.create_close(JAN_10)

        r = self.put_close(created['id'], ('2030-01-10T12:00:00', '2030-01-13T00:00:00'))

        self.assertEqual(r.status_code, 200)

    def test_update_close_day_overlapping_another_is_409(self):
        self.create_close(JAN_10)
        other = self.create_close(JAN_20)

        r = self.put_close(other['id'], ('2030-01-11T00:00:00', '2030-01-21T00:00:00'))

        self.assertEqual(r.status_code, 409)

    def test_update_close_day_init_after_end_is_400(self):
        created = self.create_close(JAN_10)

        r = self.put_close(created['id'], (JAN_10[1], JAN_10[0]))

        self.assertEqual(r.status_code, 400)

    def test_update_unknown_close_day_is_404(self):
        r = self.put_close('does-not-exist', JAN_10)

        self.assertEqual(r.status_code, 404)

    def test_update_close_day_requires_authentication(self):
        created = self.create_close(JAN_10)

        r = self.put_close(created['id'], JAN_20, headers=False)

        self.assertEqual(r.status_code, 401)

    def test_update_close_day_forbidden_for_worker_session(self):
        created = self.create_close(JAN_10)

        r = self.put_close(created['id'], JAN_20, token=self.worker_token())

        self.assertEqual(r.status_code, 401)

    # --- DELETE /close/<id> ---

    def test_delete_close_day(self):
        created = self.create_close(JAN_10)

        r = self.delete_close(created['id'])

        self.assertEqual(r.status_code, 204)
        self.assertEqual(self.get_close().json, [])

    def test_delete_unknown_close_day_is_404(self):
        r = self.delete_close('does-not-exist')

        self.assertEqual(r.status_code, 404)

    def test_delete_close_day_requires_authentication(self):
        created = self.create_close(JAN_10)

        r = self.delete_close(created['id'], headers=False)

        self.assertEqual(r.status_code, 401)

    def test_delete_close_day_forbidden_for_worker_session(self):
        created = self.create_close(JAN_10)

        r = self.delete_close(created['id'], token=self.worker_token())

        self.assertEqual(r.status_code, 401)

    # resources/close.py PUT/DELETE look the row up by id only, with no check against the caller's local.
    def test_other_local_cannot_delete_a_close_day(self):
        created = self.create_close(JAN_10)
        other = self.create_other_local()

        r = self.delete_close(created['id'], token=other['refresh_token'])

        self.assertIn(r.status_code, (403, 404))

    def test_other_local_cannot_update_a_close_day(self):
        created = self.create_close(JAN_10)
        other = self.create_other_local()

        r = self.put_close(created['id'], JAN_20, token=other['refresh_token'])

        self.assertIn(r.status_code, (403, 404))
