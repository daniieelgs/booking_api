"""helpers/security.py: passwords, encryption, JWT creation and the hand-rolled admin check."""
import datetime
import string
import unittest
from types import SimpleNamespace

import jwt
from cryptography.fernet import Fernet, InvalidToken
from flask_jwt_extended import decode_token

from db import db
from globals import ADMIN_IDENTITY, ADMIN_ROLE, LOCAL_ROLE, PASSWORD_SIZE, SECRET_JWT, USER_ROLE
from helpers import security
from helpers.error.SecurityError.AdminTokenIdentityException import AdminTokenIdentityException
from helpers.error.SecurityError.AdminTokenRoleException import AdminTokenRoleException
from helpers.error.SecurityError.NoTokenProvidedException import NoTokenProvidedException
from helpers.error.SecurityError.TokenNotFound import TokenNotFoundException
from models.session_token import SessionTokenModel
from tests.unit.db_support import DbTestCase


class TestGeneratePassword(unittest.TestCase):

    def test_default_size(self):
        self.assertEqual(len(security.generatePassword()), PASSWORD_SIZE)

    def test_custom_size(self):
        self.assertEqual(len(security.generatePassword(40)), 40)

    def test_only_letters_digits_and_punctuation(self):
        allowed = set(string.ascii_letters + string.digits + string.punctuation)

        self.assertTrue(set(security.generatePassword(500)) <= allowed)

    def test_two_passwords_differ(self):
        self.assertNotEqual(security.generatePassword(32), security.generatePassword(32))


class TestEncryption(unittest.TestCase):

    def test_roundtrip(self):
        self.assertEqual(security.decrypt_str(security.encrypt_str('s3cret-smtp-pass')), 's3cret-smtp-pass')

    def test_roundtrip_with_unicode(self):
        self.assertEqual(security.decrypt_str(security.encrypt_str('contraseña-ñ-€')), 'contraseña-ñ-€')

    def test_ciphertext_does_not_contain_the_plaintext(self):
        self.assertNotIn(b'secret', security.encrypt_str('secret'))

    def test_same_text_encrypts_differently_each_time(self):
        self.assertNotEqual(security.encrypt_str('same'), security.encrypt_str('same'))

    def test_wrong_key_cannot_decrypt(self):
        token = security.encrypt_str('secret')

        with self.assertRaises(InvalidToken):
            security.decrypt_str(token, key=Fernet.generate_key())

    def test_tampered_ciphertext_is_rejected(self):
        token = bytearray(security.encrypt_str('secret'))
        middle = len(token) // 2
        token[middle] = ord('A') if token[middle] != ord('A') else ord('B')

        with self.assertRaises(InvalidToken):
            security.decrypt_str(bytes(token))

    def test_accepts_a_custom_key(self):
        key = Fernet.generate_key()

        self.assertEqual(security.decrypt_str(security.encrypt_str('x', key=key), key=key), 'x')


class TestUuid(unittest.TestCase):

    def test_is_32_hex_characters(self):
        value = security.generateUUID()

        self.assertEqual(len(value), 32)
        int(value, 16)

    def test_is_unique(self):
        self.assertEqual(len({security.generateUUID() for _ in range(200)}), 200)


class TestGenerateTokens(DbTestCase):

    def test_refresh_only_by_default_returns_a_single_token(self):
        token = security.generateTokens('identity-1', 'local-1')

        self.assertIsInstance(token, str)
        self.assertEqual(decode_token(token)['type'], 'refresh')
        self.assertEqual(decode_token(token)['sub'], 'identity-1')

    def test_access_only_returns_a_fresh_access_token(self):
        token = security.generateTokens('identity-1', 'local-1', access_token=True, refresh_token=False)

        decoded = decode_token(token)
        self.assertEqual(decoded['type'], 'access')
        self.assertTrue(decoded['fresh'])

    def test_both_returns_the_access_and_refresh_tokens_in_that_order(self):
        access, refresh = security.generateTokens('identity-1', 'local-1', access_token=True, refresh_token=True)

        self.assertEqual(decode_token(access)['type'], 'access')
        self.assertEqual(decode_token(refresh)['type'], 'refresh')

    def test_each_token_is_stored_with_its_own_id_and_jti(self):
        access, refresh = security.generateTokens('identity-1', 'local-1', access_token=True, refresh_token=True)

        stored = {row.id: row for row in SessionTokenModel.query.all()}

        self.assertEqual(len(stored), 2)
        for token in (access, refresh):
            decoded = decode_token(token)
            self.assertEqual(stored[decoded['token']].jti, decoded['jti'])

    def test_token_ids_are_unique_between_calls(self):
        security.generateTokens('identity-1', 'local-1')
        security.generateTokens('identity-1', 'local-1')

        self.assertEqual(SessionTokenModel.query.count(), 2)

    def test_the_stored_row_belongs_to_the_local_and_the_role(self):
        security.generateTokens('identity-1', 'local-1', user_role=USER_ROLE, user_id=7)

        row = SessionTokenModel.query.one()
        self.assertEqual(row.local_id, 'local-1')
        self.assertEqual(row.user_session.user, USER_ROLE)
        self.assertEqual(row.user_id, 7)

    def test_default_role_is_local(self):
        security.generateTokens('identity-1', 'local-1')

        self.assertEqual(SessionTokenModel.query.one().user_session.user, LOCAL_ROLE)

    def test_refresh_token_honours_the_requested_lifetime(self):
        token = security.generateTokens('identity-1', 'local-1', expire_refresh=datetime.timedelta(hours=2))

        decoded = decode_token(token)
        self.assertEqual(decoded['exp'] - decoded['iat'], 2 * 3600)

    def test_access_token_honours_the_requested_lifetime(self):
        token = security.generateTokens('identity-1', 'local-1', access_token=True, refresh_token=False,
                                        expire_access=datetime.timedelta(minutes=10))

        decoded = decode_token(token)
        self.assertEqual(decoded['exp'] - decoded['iat'], 600)

    def test_additional_claims_are_included(self):
        token = security.generateTokens('identity-1', 'local-1', claims={'extra': 'yes'})

        self.assertEqual(decode_token(token)['extra'], 'yes')

    def test_get_token_id_returns_the_stored_id(self):
        token = security.generateTokens('identity-1', 'local-1')

        self.assertEqual(security.getTokenId(token), SessionTokenModel.query.one().id)

    def test_an_already_expired_lifetime_fails_while_the_token_is_stored(self):
        # the function decodes the token it just created in order to store it, so it cannot return an expired one
        with self.assertRaises(jwt.ExpiredSignatureError):
            security.generateTokens('identity-1', 'local-1', expire_refresh=datetime.timedelta(seconds=-5))

    def test_log_out_all_removes_only_that_locals_tokens(self):
        security.generateTokens('identity-1', 'local-1')
        security.generateTokens('identity-1', 'local-1')
        security.generateTokens('identity-2', 'local-2')

        security.logOutAll('local-1')

        self.assertEqual([row.local_id for row in SessionTokenModel.query.all()], ['local-2'])


class TestDecodeJwt(DbTestCase):

    def test_decodes_a_token_signed_with_the_app_secret(self):
        token = security.generateTokens('identity-1', 'local-1')

        self.assertEqual(security.decodeJWT(token)['sub'], 'identity-1')

    def test_rejects_a_token_signed_with_another_secret(self):
        forged = jwt.encode({'sub': ADMIN_IDENTITY, 'token': 'x'}, 'another-secret', algorithm='HS256')

        with self.assertRaises(jwt.InvalidSignatureError):
            security.decodeJWT(forged)

    def test_rejects_an_unsigned_token(self):
        unsigned = jwt.encode({'sub': ADMIN_IDENTITY, 'token': 'x'}, key=None, algorithm='none')

        with self.assertRaises(jwt.InvalidAlgorithmError):
            security.decodeJWT(unsigned)

    def test_rejects_garbage(self):
        with self.assertRaises(jwt.DecodeError):
            security.decodeJWT('not-a-jwt')

    def test_rejects_an_expired_token(self):
        expired = jwt.encode({'sub': 'x', 'exp': datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=5)},
                             SECRET_JWT, algorithm='HS256')

        with self.assertRaises(jwt.ExpiredSignatureError):
            security.decodeJWT(expired)


class TestCheckAdminToken(DbTestCase):

    def admin_token(self, identity=ADMIN_IDENTITY, role=ADMIN_ROLE):
        return security.generateTokens(identity, None, user_role=role)

    def test_valid_admin_token_returns_its_id_and_identity(self):
        token = self.admin_token()

        token_id, identity = security.check_admin_token(token)

        self.assertEqual(token_id, security.getTokenId(token))
        self.assertEqual(identity, ADMIN_IDENTITY)

    def test_other_identity_is_rejected(self):
        with self.assertRaises(AdminTokenIdentityException):
            security.check_admin_token(self.admin_token(identity='someone-else'))

    def test_admin_identity_with_a_non_admin_role_is_rejected(self):
        with self.assertRaises(AdminTokenRoleException):
            security.check_admin_token(self.admin_token(role=LOCAL_ROLE))

    def test_revoked_token_is_rejected(self):
        token = self.admin_token()
        SessionTokenModel.query.delete()
        db.session.commit()

        with self.assertRaises(TokenNotFoundException):
            security.check_admin_token(token)

    def test_token_signed_with_another_secret_is_rejected(self):
        self.admin_token()
        forged = jwt.encode({'sub': ADMIN_IDENTITY, 'token': SessionTokenModel.query.one().id}, 'another-secret',
                            algorithm='HS256')

        with self.assertRaises(jwt.InvalidSignatureError):
            security.check_admin_token(forged)

    def test_expired_admin_token_is_rejected(self):
        self.admin_token()
        token = jwt.encode({'sub': ADMIN_IDENTITY, 'token': SessionTokenModel.query.one().id,
                            'exp': datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=5)},
                           SECRET_JWT, algorithm='HS256')

        with self.assertRaises(jwt.ExpiredSignatureError):
            security.check_admin_token(token)

    def test_garbage_is_rejected(self):
        with self.assertRaises(jwt.DecodeError):
            security.check_admin_token('nope')


class TestCheckAdminRequest(DbTestCase):

    def request(self, header=None):
        return SimpleNamespace(headers={'Authorization': header} if header is not None else {})

    def test_missing_header_is_rejected(self):
        with self.assertRaises(NoTokenProvidedException):
            security.check_admin_request(self.request())

    def test_header_without_bearer_prefix_is_rejected(self):
        with self.assertRaises(NoTokenProvidedException):
            security.check_admin_request(self.request('Basic abc'))

    def test_empty_header_is_rejected(self):
        with self.assertRaises(NoTokenProvidedException):
            security.check_admin_request(self.request(''))

    def test_valid_bearer_token_is_accepted(self):
        token = security.generateTokens(ADMIN_IDENTITY, None, user_role=ADMIN_ROLE)

        _, identity = security.check_admin_request(self.request(f'Bearer {token}'))

        self.assertEqual(identity, ADMIN_IDENTITY)

    def test_bearer_prefix_is_case_sensitive(self):
        token = security.generateTokens(ADMIN_IDENTITY, None, user_role=ADMIN_ROLE)

        with self.assertRaises(NoTokenProvidedException):
            security.check_admin_request(self.request(f'bearer {token}'))


if __name__ == '__main__':
    unittest.main()
