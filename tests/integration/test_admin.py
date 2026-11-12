import datetime
import json

import jwt
from flask_testing import TestCase

from app import create_app, db
from globals import ADMIN_IDENTITY, JWT_ALGORITHM, SECRET_JWT
from tests.config_test import config_test, getUrl, setParams
from tests.configure_local_base import LocalBase


class TestAdmin(TestCase):

    def create_app(self):
        app = create_app(config_test)
        self.locals = []
        return app

    def setUp(self):
        db.create_all()
        config_test.config(db=db)
        self.admin_token = config_test.ADMIN_TOKEN

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        config_test.drop(self.locals)

    def create_local(self):
        base = LocalBase(self.client, self.admin_token, self.assertEqual)
        base.create_local(-1, set_local_settings=False, set_smtp_settings=False)
        self.locals.extend(base.locals)
        return base

    def bearer(self, token):
        return {'Authorization': f'Bearer {token}'}

    def forged_token(self, token_id, expires_in=datetime.timedelta(hours=1)):
        payload = {
            'sub': ADMIN_IDENTITY,
            'token': token_id,
            'exp': datetime.datetime.utcnow() + expires_in,
        }
        return jwt.encode(payload, SECRET_JWT, algorithm=JWT_ALGORITHM)

    def post_local_tokens(self, local_id, token=None):
        headers = self.bearer(token) if token else {}
        return self.client.post(getUrl('admin', 'tokens', 'local', local_id), headers=headers)

    def get_all_locals(self, token=None, **params):
        headers = self.bearer(token) if token else {}
        url = setParams(getUrl('admin', 'local', 'all'), **params) if params else getUrl('admin', 'local', 'all')
        return self.client.get(url, headers=headers)

    # --- POST admin/tokens/local/<local_id> ---

    def test_local_tokens_returns_tokens_and_local(self):
        local = self.create_local()

        r = self.post_local_tokens(local.local['id'], self.admin_token)

        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json['access_token'])
        self.assertTrue(r.json['refresh_token'])
        self.assertEqual(r.json['local']['id'], local.local['id'])

    def test_local_tokens_are_usable_as_local_session(self):
        local = self.create_local()
        tokens = self.post_local_tokens(local.local['id'], self.admin_token).json

        r = self.client.get(getUrl('close'), headers=self.bearer(tokens['refresh_token']))

        self.assertEqual(r.status_code, 200)

    def test_local_tokens_missing_authorization_header(self):
        local = self.create_local()

        r = self.post_local_tokens(local.local['id'])

        self.assertEqual(r.status_code, 401)

    def test_local_tokens_non_bearer_header(self):
        local = self.create_local()

        r = self.client.post(getUrl('admin', 'tokens', 'local', local.local['id']), headers={'Authorization': self.admin_token})

        self.assertEqual(r.status_code, 401)

    def test_local_tokens_expired_token(self):
        local = self.create_local()
        token = self.forged_token('any-token-id', expires_in=-datetime.timedelta(hours=1))

        r = self.post_local_tokens(local.local['id'], token)

        self.assertEqual(r.status_code, 401)

    def test_local_tokens_rejects_local_session_token(self):
        local = self.create_local()

        r = self.post_local_tokens(local.local['id'], local.refresh_token)

        self.assertEqual(r.status_code, 403)

    def test_local_tokens_rejects_admin_identity_with_non_admin_session(self):
        local = self.create_local()
        local_token_id = jwt.decode(local.refresh_token, SECRET_JWT, algorithms=[JWT_ALGORITHM])['token']

        r = self.post_local_tokens(local.local['id'], self.forged_token(local_token_id))

        self.assertEqual(r.status_code, 403)

    def test_local_tokens_unknown_session_token_is_404(self):
        local = self.create_local()

        r = self.post_local_tokens(local.local['id'], self.forged_token('does-not-exist'))

        self.assertEqual(r.status_code, 404)

    def test_local_tokens_unknown_local_is_404(self):
        r = self.post_local_tokens('does-not-exist', self.admin_token)

        self.assertEqual(r.status_code, 404)

    # --- GET admin/local/all ---

    def test_local_all_lists_every_local(self):
        local = self.create_local()

        r = self.get_all_locals(self.admin_token)

        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json['total'], 1)
        self.assertEqual([l['id'] for l in r.json['locals']], [local.local['id']])

    def test_local_all_empty_when_there_are_no_locals(self):
        r = self.get_all_locals(self.admin_token)

        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json['total'], 0)
        self.assertEqual(r.json['locals'], [])

    def test_local_all_filters_by_name(self):
        local = self.create_local()

        found = self.get_all_locals(self.admin_token, name=local.local['name'])
        missing = self.get_all_locals(self.admin_token, name='no-such-local-name')

        self.assertEqual(found.status_code, 200)
        self.assertEqual(found.json['total'], 1)
        self.assertEqual(missing.status_code, 200)
        self.assertEqual(missing.json['total'], 0)

    def test_local_all_missing_authorization_header(self):
        r = self.get_all_locals()

        self.assertEqual(r.status_code, 401)

    def test_local_all_expired_token(self):
        r = self.get_all_locals(self.forged_token('any-token-id', expires_in=-datetime.timedelta(hours=1)))

        self.assertEqual(r.status_code, 401)

    def test_local_all_rejects_local_session_token(self):
        local = self.create_local()

        r = self.get_all_locals(local.refresh_token)

        self.assertEqual(r.status_code, 403)

    def test_local_all_rejects_admin_identity_with_non_admin_session(self):
        local = self.create_local()
        local_token_id = jwt.decode(local.refresh_token, SECRET_JWT, algorithms=[JWT_ALGORITHM])['token']

        r = self.get_all_locals(self.forged_token(local_token_id))

        self.assertEqual(r.status_code, 403)

    def test_local_all_unknown_session_token_is_404(self):
        r = self.get_all_locals(self.forged_token('does-not-exist'))

        self.assertEqual(r.status_code, 404)
