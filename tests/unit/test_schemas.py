"""schema.py: what the API accepts and rejects at its boundary (Marshmallow only, no Flask)."""
import datetime
import unittest
from types import SimpleNamespace

from marshmallow import ValidationError

import schema
from globals import TIMEOUT_CONFIRM_BOOKING
from helpers.security import decrypt_str


class SchemaTestCase(unittest.TestCase):

    def errors(self, schema_class, data, **kwargs):
        with self.assertRaises(ValidationError) as context:
            schema_class(**kwargs).load(data)
        return context.exception.messages

    def assertRejects(self, schema_class, data, field):
        self.assertIn(field, self.errors(schema_class, data))

    def assertAccepts(self, schema_class, data):
        return schema_class().load(data)


SMTP = {'name': 'brevo', 'host': 'smtp-relay.brevo.com', 'port': 587, 'user': 'user@x.com', 'mail': 'info@x.com',
        'password': 'secret', 'priority': 10}


class TestSmtpSettingsSchema(SchemaTestCase):

    def test_valid_payload_with_defaults(self):
        loaded = self.assertAccepts(schema.SmtpSettingsSchema, dict(SMTP))

        self.assertEqual((loaded['send_per_day'], loaded['send_per_month']), (0, 0))

    def test_password_is_encrypted_on_load_and_never_kept_in_clear(self):
        loaded = self.assertAccepts(schema.SmtpSettingsSchema, dict(SMTP))

        self.assertNotEqual(loaded['password'], 'secret')
        self.assertEqual(decrypt_str(loaded['password'].encode()), 'secret')

    def test_password_is_decrypted_on_dump(self):
        stored = SimpleNamespace(**{**SMTP, 'password': schema.encrypt_str('secret').decode(), 'send_per_day': 0,
                                    'send_per_month': 0})

        self.assertEqual(schema.SmtpSettingsSchema().dump(stored)['password'], 'secret')

    def test_required_fields(self):
        for field in ('name', 'host', 'port', 'user', 'mail', 'password', 'priority'):
            with self.subTest(field=field):
                data = {k: v for k, v in SMTP.items() if k != field}

                self.assertRejects(schema.SmtpSettingsSchema, data, field)

    def test_invalid_values(self):
        cases = [('mail', 'not-an-email'), ('port', 70000), ('port', -1), ('priority', -1), ('name', 'ab')]
        for field, value in cases:
            with self.subTest(field=field, value=value):
                self.assertRejects(schema.SmtpSettingsSchema, {**SMTP, field: value}, field)

    def test_negative_counters_are_rejected(self):
        self.assertRejects(schema.SmtpSettingsSchema, {**SMTP, 'send_per_day': -1}, 'send_per_day')

    def test_reset_dates_are_parsed(self):
        loaded = self.assertAccepts(schema.SmtpSettingsSchema, {**SMTP, 'reset_send_per_day': '2030-01-02T00:00:00'})

        self.assertEqual(loaded['reset_send_per_day'], datetime.datetime(2030, 1, 2))

    def test_patch_schema_only_requires_the_name(self):
        loaded = self.assertAccepts(schema.SmtpSettingsPatchSchema, {'name': 'brevo', 'remove': True})

        self.assertTrue(loaded['remove'])
        self.assertRejects(schema.SmtpSettingsPatchSchema, {'remove': True}, 'name')

    def test_patch_schema_allows_clearing_the_caps(self):
        loaded = self.assertAccepts(schema.SmtpSettingsPatchSchema, {'name': 'brevo', 'max_send_per_day': None})

        self.assertIsNone(loaded['max_send_per_day'])


class TestSettingsSchemas(SchemaTestCase):

    def test_urls_must_be_urls(self):
        for field in ('website', 'instagram', 'facebook', 'twitter', 'whatsapp', 'linkedin', 'tiktok', 'maps'):
            with self.subTest(field=field):
                self.assertAccepts(schema.PublicSettingsSchema, {field: 'https://example.com/x'})
                self.assertRejects(schema.PublicSettingsSchema, {field: 'not a url'}, field)

    def test_contact_fields(self):
        self.assertRejects(schema.PublicSettingsSchema, {'email_contact': 'nope'}, 'email_contact')
        self.assertRejects(schema.PublicSettingsSchema, {'email_support': 'nope'}, 'email_support')
        self.assertRejects(schema.PublicSettingsSchema, {'phone_contact': '12345'}, 'phone_contact')
        self.assertAccepts(schema.PublicSettingsSchema, {'phone_contact': '+34 600000000'})

    def test_booking_timeout_defaults_when_missing(self):
        self.assertEqual(self.assertAccepts(schema.LocalSettingsSchema, {})['booking_timeout'], TIMEOUT_CONFIRM_BOOKING)

    def test_booking_timeout_accepts_disabled_and_none(self):
        self.assertEqual(self.assertAccepts(schema.LocalSettingsSchema, {'booking_timeout': -1})['booking_timeout'], -1)
        self.assertIsNone(self.assertAccepts(schema.LocalSettingsSchema, {'booking_timeout': None})['booking_timeout'])

    def test_booking_timeout_below_minus_one_is_rejected(self):
        self.assertRejects(schema.LocalSettingsSchema, {'booking_timeout': -2}, 'booking_timeout')

    def test_patch_does_not_inject_a_default_timeout(self):
        self.assertNotIn('booking_timeout', self.assertAccepts(schema.LocalSettingsPatchSchema, {}))

    def test_link_templates_must_be_urls(self):
        self.assertRejects(schema.LocalSettingsSchema, {'confirmation_link': 'nope'}, 'confirmation_link')
        self.assertRejects(schema.LocalSettingsSchema, {'cancel_link': 'nope'}, 'cancel_link')

    def test_smtp_settings_are_validated_as_a_nested_list(self):
        self.assertRejects(schema.LocalSettingsSchema, {'smtp_settings': [{**SMTP, 'mail': 'bad'}]}, 'smtp_settings')
        self.assertEqual(len(self.assertAccepts(schema.LocalSettingsSchema, {'smtp_settings': [dict(SMTP)]})['smtp_settings']), 1)


LOCAL = {'name': 'Sublime', 'tlf': '600000000', 'email': 'info@sublime.com', 'location': 'Europe/Madrid'}


class TestLocalSchemas(SchemaTestCase):

    def test_valid_local(self):
        loaded = self.assertAccepts(schema.LocalSchema, dict(LOCAL))

        self.assertEqual(loaded['name'], 'Sublime')

    def test_required_fields(self):
        for field in LOCAL:
            with self.subTest(field=field):
                self.assertRejects(schema.LocalSchema, {k: v for k, v in LOCAL.items() if k != field}, field)

    def test_invalid_values(self):
        cases = [('name', 'ab'), ('name', 'x' * 46), ('tlf', '12345'), ('tlf', '1' * 14), ('email', 'nope')]
        for field, value in cases:
            with self.subTest(field=field, value=value):
                self.assertRejects(schema.LocalSchema, {**LOCAL, field: value}, field)

    def test_server_generated_fields_cannot_be_set_by_the_client(self):
        for field in ('id', 'password_generated', 'uuid_log', 'datetime_created', 'datetime_updated'):
            with self.subTest(field=field):
                self.assertRejects(schema.LocalSchema, {**LOCAL, field: 'x'}, field)

    def test_password_can_be_sent_but_is_never_returned(self):
        loaded = self.assertAccepts(schema.LocalSchema, {**LOCAL, 'password': 'pw'})
        stored = SimpleNamespace(**{**LOCAL, 'id': 'l1', 'password': 'hash', 'password_generated': None,
                                    'description': None, 'address': None, 'postal_code': None, 'village': None,
                                    'province': None, 'local_settings': None, 'uuid_log': None,
                                    'datetime_created': datetime.datetime(2030, 1, 1),
                                    'datetime_updated': datetime.datetime(2030, 1, 1)})

        self.assertEqual(loaded['password'], 'pw')
        self.assertNotIn('password', schema.LocalSchema().dump(stored))

    def test_public_schema_does_not_expose_contact_or_private_fields(self):
        dumped = schema.PublicLocalSchema().dump(SimpleNamespace(**{**LOCAL, 'id': 'l1', 'password': 'hash',
                                                                   'description': 'd', 'address': 'a', 'postal_code': '1',
                                                                   'village': 'v', 'province': 'p', 'local_settings': None}))

        self.assertNotIn('password', dumped)
        self.assertNotIn('tlf', dumped)
        self.assertNotIn('email', dumped)

    def test_patch_schema_accepts_a_partial_update_and_nothing_required(self):
        self.assertEqual(self.assertAccepts(schema.LocalPatchSchema, {'name': 'New name'}), {'name': 'New name'})
        self.assertEqual(self.assertAccepts(schema.LocalPatchSchema, {}), {})

    def test_patch_schema_still_validates_what_is_sent(self):
        self.assertRejects(schema.LocalPatchSchema, {'email': 'nope'}, 'email')

    def test_login_requires_email_and_password(self):
        self.assertRejects(schema.LoginLocalSchema, {'email': 'a@b.com'}, 'password')
        self.assertRejects(schema.LoginLocalSchema, {'password': 'x'}, 'email')


class TestCatalogSchemas(SchemaTestCase):

    def test_service(self):
        loaded = self.assertAccepts(schema.ServiceSchema, {'name': 'Corte', 'duration': 30, 'price': 12.5, 'work_group': 1})

        self.assertEqual((loaded['duration'], loaded['price']), (30, 12.5))

    def test_service_rejects_negative_numbers_and_short_names(self):
        base = {'name': 'Corte', 'duration': 30, 'price': 12.5, 'work_group': 1}
        for field, value in (('duration', -1), ('price', -0.5), ('name', 'ab')):
            with self.subTest(field=field):
                self.assertRejects(schema.ServiceSchema, {**base, field: value}, field)

    def test_service_requires_its_work_group(self):
        self.assertRejects(schema.ServiceSchema, {'name': 'Corte', 'duration': 30, 'price': 1}, 'work_group')

    def test_service_work_group_is_not_dumped(self):
        dumped = schema.ServiceSchema().dump(SimpleNamespace(id=1, name='Corte', description=None, duration=30, price=1.0,
                                                             work_group=3, datetime_created=None, datetime_updated=None))

        self.assertNotIn('work_group', dumped)

    def test_work_group(self):
        self.assertAccepts(schema.WorkGroupSchema, {'name': 'Peluquería'})
        self.assertRejects(schema.WorkGroupSchema, {'name': 'ab'}, 'name')
        self.assertRejects(schema.WorkGroupSchema, {}, 'name')

    def test_worker_requires_its_work_groups(self):
        self.assertRejects(schema.WorkerSchema, {'name': 'Ana'}, 'work_groups')
        self.assertEqual(self.assertAccepts(schema.WorkerSchema, {'name': 'Ana', 'work_groups': [1, 2]})['work_groups'], [1, 2])

    def test_worker_optional_fields(self):
        loaded = self.assertAccepts(schema.WorkerSchema, {'name': 'Ana', 'work_groups': [1], 'tlf': None, 'password': None})

        self.assertIsNone(loaded['tlf'])
        self.assertRejects(schema.WorkerSchema, {'name': 'Ana', 'work_groups': [1], 'email': 'nope'}, 'email')
        self.assertRejects(schema.WorkerSchema, {'name': 'Ana', 'work_groups': ['x']}, 'work_groups')

    def test_worker_password_is_never_dumped(self):
        dumped = schema.WorkerSchema().dump(SimpleNamespace(id=1, name='Ana', last_name=None, image=None, email='a@b.com',
                                                            tlf=None, password='hash', datetime_created=None,
                                                            datetime_updated=None, work_groups=[]))

        self.assertNotIn('password', dumped)
        self.assertNotIn('work_groups', dumped)


class TestTimetableSchema(SchemaTestCase):

    def test_times_are_parsed(self):
        loaded = self.assertAccepts(schema.TimetableSchema, {'opening_time': '09:00:00', 'closing_time': '13:30:00',
                                                             'weekday_short': 'MO'})

        self.assertEqual(loaded['opening_time'], datetime.time(9, 0))
        self.assertEqual(loaded['closing_time'], datetime.time(13, 30))

    def test_invalid_times_are_rejected(self):
        for value in ('25:00:00', 'nine', '', 900):
            with self.subTest(value=value):
                self.assertRejects(schema.TimetableSchema, {'opening_time': value, 'closing_time': '13:00:00',
                                                            'weekday_short': 'MO'}, 'opening_time')

    def test_required_fields(self):
        base = {'opening_time': '09:00:00', 'closing_time': '13:00:00', 'weekday_short': 'MO'}
        for field in base:
            with self.subTest(field=field):
                self.assertRejects(schema.TimetableSchema, {k: v for k, v in base.items() if k != field}, field)


BOOKING = {'client_name': 'Daniel', 'client_email': 'daniel@x.com', 'client_tlf': '600000000',
           'datetime_init': '2030-01-01 10:00:00', 'services_ids': [1, 2]}


class TestBookingSchemas(SchemaTestCase):

    def test_valid_booking_with_a_space_separated_datetime(self):
        loaded = self.assertAccepts(schema.BookingSchema, dict(BOOKING))

        self.assertEqual(loaded['datetime_init'], datetime.datetime(2030, 1, 1, 10, 0))
        self.assertEqual(loaded['services_ids'], [1, 2])

    def test_iso_datetime_is_accepted_too(self):
        loaded = self.assertAccepts(schema.BookingSchema, {**BOOKING, 'datetime_init': '2030-01-01T10:00:00'})

        self.assertEqual(loaded['datetime_init'], datetime.datetime(2030, 1, 1, 10, 0))

    def test_worker_is_optional(self):
        self.assertNotIn('worker_id', self.assertAccepts(schema.BookingSchema, dict(BOOKING)))
        self.assertEqual(self.assertAccepts(schema.BookingSchema, {**BOOKING, 'worker_id': 4})['worker_id'], 4)

    def test_required_fields(self):
        for field in BOOKING:
            with self.subTest(field=field):
                self.assertRejects(schema.BookingSchema, {k: v for k, v in BOOKING.items() if k != field}, field)

    def test_invalid_values(self):
        cases = [('client_name', 'ab'), ('client_name', 'x' * 46), ('client_email', 'nope'), ('client_tlf', '123'),
                 ('datetime_init', 'tomorrow'), ('datetime_init', '2030-13-01 10:00:00'), ('services_ids', 'abc'),
                 ('services_ids', ['x'])]
        for field, value in cases:
            with self.subTest(field=field, value=value):
                self.assertRejects(schema.BookingSchema, {**BOOKING, field: value}, field)

    def test_server_controlled_fields_cannot_be_set_by_the_client(self):
        for field in ('id', 'datetime_end', 'status', 'total_price', 'uuid_log', 'server_name', 'services'):
            with self.subTest(field=field):
                self.assertRejects(schema.BookingSchema, {**BOOKING, field: 'x'}, field)

    def test_unknown_fields_are_rejected(self):
        self.assertRejects(schema.BookingSchema, {**BOOKING, 'is_admin': True}, 'is_admin')

    def test_patch_accepts_any_subset(self):
        self.assertEqual(self.assertAccepts(schema.BookingPatchSchema, {}), {})
        self.assertEqual(self.assertAccepts(schema.BookingPatchSchema, {'comment': 'hola'}), {'comment': 'hola'})

    def test_patch_still_validates_what_is_sent(self):
        self.assertRejects(schema.BookingPatchSchema, {'client_email': 'nope'}, 'client_email')
        self.assertRejects(schema.BookingPatchSchema, {'datetime_init': 'tomorrow'}, 'datetime_init')

    def test_admin_schema_requires_the_new_status(self):
        self.assertRejects(schema.BookingAdminSchema, dict(BOOKING), 'new_status')
        self.assertEqual(self.assertAccepts(schema.BookingAdminSchema, {**BOOKING, 'new_status': 'C'})['new_status'], 'C')

    def test_worker_booking_does_not_take_client_contact_details(self):
        self.assertRejects(schema.WorkerBookingSchema, {'client_name': 'Daniel', 'client_email': 'a@b.com',
                                                        'datetime_init': '2030-01-01 10:00:00', 'services_ids': [1]},
                           'client_email')

    def test_new_booking_response_dumps_the_session_token_and_timeout(self):
        dumped = schema.NewBookingSchema().dump({'booking': {}, 'session_token': 'T', 'timeout': 60, 'email_confirm': True})

        self.assertEqual((dumped['session_token'], dumped['timeout'], dumped['email_confirm']), ('T', 60.0, True))


class TestQueryParamSchemas(SchemaTestCase):

    def test_booking_params_parse_dates_and_flags(self):
        loaded = self.assertAccepts(schema.BookingParams, {'date': '2030-01-01', 'free': 'true', 'worker_id': '3'})

        self.assertEqual(loaded, {'date': datetime.date(2030, 1, 1), 'free': True, 'worker_id': 3})

    def test_booking_params_reject_bad_values(self):
        self.assertRejects(schema.BookingParams, {'date': 'yesterday'}, 'date')
        self.assertRejects(schema.BookingParams, {'worker_id': 'abc'}, 'worker_id')
        self.assertRejects(schema.BookingParams, {'free': 'maybe'}, 'free')

    def test_week_params_add_the_number_of_days(self):
        self.assertEqual(self.assertAccepts(schema.BookingWeekParams, {'days': '5'})['days'], 5)

    def test_admin_params_add_status_and_client_filters(self):
        loaded = self.assertAccepts(schema.BookingAdminParams, {'status': 'C,P', 'name': 'Ana', 'email': 'a@', 'tlf': '60'})

        self.assertEqual(loaded['status'], 'C,P')

    def test_delete_and_update_params(self):
        self.assertEqual(self.assertAccepts(schema.DeleteParams, {'force': 'true', 'comment': 'x'}), {'force': True, 'comment': 'x'})
        self.assertEqual(self.assertAccepts(schema.UpdateParams, {'notify': 'false', 'force': 'true'}), {'notify': False, 'force': True})

    def test_local_admin_params_filter_by_creation_dates(self):
        loaded = self.assertAccepts(schema.LocalAdminParams, {'datetime_init': '2030-01-01T00:00:00', 'name': 'Sub'})

        self.assertEqual(loaded['datetime_init'], datetime.datetime(2030, 1, 1))

    def test_close_days_params(self):
        self.assertRejects(schema.CloseDaysParams, {'datetime_init': 'x'}, 'datetime_init')


class TestCloseDaysSchema(SchemaTestCase):

    def test_valid(self):
        loaded = self.assertAccepts(schema.CloseDaysSchema, {'datetime_init': '2030-08-01T00:00:00',
                                                             'datetime_end': '2030-08-15T00:00:00', 'description': 'Vacaciones'})

        self.assertEqual(loaded['datetime_end'], datetime.datetime(2030, 8, 15))

    def test_dates_are_required(self):
        self.assertRejects(schema.CloseDaysSchema, {'datetime_end': '2030-08-15T00:00:00'}, 'datetime_init')
        self.assertRejects(schema.CloseDaysSchema, {'datetime_init': '2030-08-15T00:00:00'}, 'datetime_end')

    def test_id_is_server_generated(self):
        self.assertRejects(schema.CloseDaysSchema, {'id': 1, 'datetime_init': '2030-08-01T00:00:00',
                                                    'datetime_end': '2030-08-15T00:00:00'}, 'id')


class TestResponseOnlySchemas(SchemaTestCase):

    def test_health_dumps_only_the_status(self):
        self.assertEqual(schema.HealthSchema().dump({'status': 'ok', 'redis': 'ok', 'db': 'secret'}), {'status': 'ok'})

    def test_version(self):
        self.assertEqual(schema.VersionSchema().dump({'version': '1.2.3', 'commit': 'abc'}), {'version': '1.2.3'})

    def test_response_fields_cannot_be_loaded(self):
        self.assertRejects(schema.HealthSchema, {'status': 'ok'}, 'status')
        self.assertRejects(schema.VersionSchema, {'version': '1'}, 'version')

    def test_list_schemas_report_the_total(self):
        self.assertEqual(schema.WorkGroupListSchema().dump({'total': 0, 'work_groups': []}), {'total': 0, 'work_groups': []})


if __name__ == '__main__':
    unittest.main()
