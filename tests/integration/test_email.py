# python -m pytest tests/integration/test_email.py -v
#
# Email behaviour of the booking flow (confirmation, cancellation, update, notifications, SMTP quotas).
#
# Every test is independent: setUp creates a fresh local and each test builds the state it needs. No test depends on
# the waiter thread (helpers/BookingEmailController.start_waiter_booking_status) except TestWaiterThread: the app is
# configured without it (TIMEOUT_CONFIRM_BOOKING=-1), and automatic cancellation is exercised by calling
# check_booking_status directly, which is exactly what the thread runs after sleeping.

import datetime
import json
import time

from dateutil.relativedelta import relativedelta
from flask_testing import TestCase

from app import create_app, db
from celery_app.tasks import check_booking_status
from globals import CANCELLED_STATUS, CONFIRMED_STATUS, PENDING_STATUS
from tests.config_test import ConfigTest, getUrl, setParams
from tests.configure_local_base import configure

ENDPOINT = 'booking'
BOOKING_TIMEOUT = 2


def midnight(days=0, months=0):
    return (datetime.datetime.now() + datetime.timedelta(days=days) + relativedelta(months=months)).strftime("%Y-%m-%dT00:00:00")


class EmailTestCase(TestCase):
    waiter = None  # seconds of the waiter thread, None = no thread

    def create_app(self):
        self.config_test = ConfigTest(waiter_booking_status=self.waiter)
        return create_app(self.config_test)

    def setUp(self):
        db.create_all()
        self.config_test.config(db=db)
        self.admin_token = self.config_test.ADMIN_TOKEN
        self.local = configure(self.client, self.admin_token, self.assertEqual, 0)  # confirmation email enabled
        opening = datetime.datetime.strptime(self.local.timetable[0]['opening_time'], "%H:%M:%S").strftime("%H:%M:%S")
        day = (datetime.datetime.now() + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
        self.booking = {
            "client_name": "Client Test",
            "client_tlf": "123456789",
            "client_email": "client@example.com",
            "datetime_init": f"{day} {opening}",
            "services_ids": [self.local.services[0]['id'], self.local.services[1]['id']]
        }

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.config_test.drop(self.local.locals)

    # --- requests ---

    def auth(self):
        return {'Authorization': f"Bearer {self.local.refresh_token}"}

    def post_booking(self, booking=None):
        return self.client.post(getUrl(ENDPOINT, 'local', self.local.local['id']), data=json.dumps(booking or self.booking), content_type='application/json')

    def post_booking_local(self, **params):
        return self.client.post(setParams(getUrl(ENDPOINT), **params), data=json.dumps(self.booking), headers=self.auth(), content_type='application/json')

    def cancel_booking(self, session):
        return self.client.delete(setParams(getUrl(ENDPOINT), session=session), content_type='application/json')

    def cancel_booking_by_local(self, booking_id, **params):
        return self.client.delete(setParams(getUrl(ENDPOINT, 'cancel', booking_id), **params), headers=self.auth(), content_type='application/json')

    def update_booking(self, session, booking):
        return self.client.put(setParams(getUrl(ENDPOINT), session=session), data=json.dumps(booking), content_type='application/json')

    def update_booking_by_local(self, booking_id, booking, **params):
        return self.client.put(setParams(getUrl(ENDPOINT, booking_id), **params), data=json.dumps(booking), headers=self.auth(), content_type='application/json')

    def confirm_booking(self, session):
        return self.client.get(setParams(getUrl(ENDPOINT, 'confirm'), session=session), content_type='application/json')

    def get_booking(self, session):
        return self.client.get(setParams(getUrl(ENDPOINT), session=session), content_type='application/json')

    def get_booking_by_local(self, booking_id):
        return self.client.get(getUrl(ENDPOINT, booking_id), headers=self.auth(), content_type='application/json')

    # --- settings ---

    def get_local_settings(self):
        return self.client.get(getUrl('local'), headers=self.auth(), content_type='application/json').json['local_settings']

    def smtp(self, index=0):
        return self.get_local_settings()['smtp_settings'][index]

    def counters(self, index=0):
        smtp = self.smtp(index)
        return smtp['send_per_day'], smtp['send_per_month']

    def update_local_settings(self):
        data = self.local.local
        local_id = data.pop('id')
        r = self.client.put(getUrl('local'), data=json.dumps(data), headers={'Authorization': f"Bearer {self.local.access_token}"}, content_type='application/json')
        self.assertEqual(r.status_code, 200)
        data['id'] = local_id

    def reset_smtp_config(self, send_per_day=0, send_per_month=0, max_send_per_day=300, max_send_per_month=1000,
                          reset_send_per_day=1, reset_send_per_month=1, edit_configs=None):
        providers = self.local.local_settings['smtp_settings']
        for i, smtp in enumerate(providers):
            if edit_configs is not None and i not in edit_configs:
                continue
            smtp['send_per_day'] = send_per_day
            smtp['send_per_month'] = send_per_month
            smtp['max_send_per_day'] = max_send_per_day
            smtp['max_send_per_month'] = max_send_per_month
            smtp['reset_send_per_day'] = midnight(days=reset_send_per_day)
            smtp['reset_send_per_month'] = midnight(days=reset_send_per_month)
        self.update_local_settings()

    def set_smtp(self, index, **fields):
        self.local.local_settings['smtp_settings'][index].update(fields)
        self.update_local_settings()

    def fill_all_providers(self, day=False, month=False):
        for smtp in self.local.local_settings['smtp_settings']:
            if day: smtp['send_per_day'] = smtp['max_send_per_day']
            if month: smtp['send_per_month'] = smtp['max_send_per_month']
        self.update_local_settings()

    def enable_send_email_confirm(self, timeout=0):
        r = self.client.patch(getUrl('local'), data=json.dumps({"local_settings": {"booking_timeout": timeout}}),
                              headers={'Authorization': f"Bearer {self.local.access_token}"}, content_type='application/json')
        self.assertEqual(r.status_code, 200)

    def disable_send_email_confirm(self):
        self.enable_send_email_confirm(-1)

    # --- assertions ---

    def create_booking(self, booking=None):
        r = self.post_booking(booking)
        self.assertEqual(r.status_code, 201, r.json)
        return r.json

    def assertEmailFlag(self, booking_id, flag, value):
        r = self.get_booking_by_local(booking_id)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json[flag], value, f'{flag} of booking {booking_id}')

    def assertCounters(self, expected, index=0):
        self.assertEqual(self.counters(index), expected)


class TestConfirmationEmail(EmailTestCase):
    """The email asking the customer to confirm the booking (enabled by local_settings.booking_timeout)."""

    def test_booking_is_pending_and_the_confirmation_email_is_requested(self):
        response = self.create_booking()

        self.assertEqual(response['booking']['status']['status'], PENDING_STATUS)
        self.assertTrue(response['email_confirm'])
        self.assertEmailFlag(response['booking']['id'], 'email_confirm', True)

    def test_sending_it_counts_once_per_day_and_per_month(self):
        pre_day, pre_month = self.counters()

        self.create_booking()

        self.assertCounters((pre_day + 1, pre_month + 1))

    def test_disabled_confirmation_confirms_the_booking_directly(self):
        self.disable_send_email_confirm()

        response = self.create_booking()

        self.assertEqual(response['booking']['status']['status'], CONFIRMED_STATUS)
        self.assertFalse(response['email_confirm'])
        self.assertEmailFlag(response['booking']['id'], 'email_confirm', False)
        self.assertEmailFlag(response['booking']['id'], 'email_confirmed', True)

    def test_when_every_provider_is_at_its_daily_limit_the_booking_is_confirmed_without_the_confirmation_email(self):
        self.reset_smtp_config(send_per_day=300, max_send_per_day=300)

        response = self.create_booking()

        self.assertFalse(response['email_confirm'])
        self.assertEqual(response['booking']['status']['status'], CONFIRMED_STATUS)
        self.assertEmailFlag(response['booking']['id'], 'email_confirm', False)


class TestSmtpQuotas(EmailTestCase):
    """Daily/monthly counters, their resets and the fallback to the next provider."""

    def test_an_expired_daily_window_resets_the_counter_and_moves_the_reset_to_tomorrow(self):
        self.reset_smtp_config(send_per_day=300, send_per_month=300, reset_send_per_day=-1, reset_send_per_month=1, edit_configs=[0])

        self.create_booking()

        self.assertCounters((1, 301))
        self.assertEqual(self.smtp()['reset_send_per_day'], midnight(days=1))

    def test_an_expired_monthly_window_resets_the_counter_and_moves_the_reset_one_month_on(self):
        self.reset_smtp_config(send_per_day=2, send_per_month=50, reset_send_per_day=1, reset_send_per_month=-1, edit_configs=[0])

        self.create_booking()

        self.assertCounters((3, 1))
        self.assertEqual(self.smtp()['reset_send_per_month'], midnight(days=-1, months=1))

    def test_a_provider_at_its_daily_limit_is_skipped_for_the_next_one(self):
        self.reset_smtp_config()
        self.set_smtp(0, send_per_day=300)
        day1 = self.smtp(1)['send_per_day']

        response = self.create_booking()

        self.assertTrue(response['email_confirm'])
        self.assertEqual(self.smtp(0)['send_per_day'], 300)
        self.assertEqual(self.smtp(1)['send_per_day'], day1 + 1)

    def test_a_provider_at_its_monthly_limit_is_skipped_for_the_next_one(self):
        self.reset_smtp_config()
        self.set_smtp(0, send_per_month=1000)
        day1 = self.smtp(1)['send_per_day']

        response = self.create_booking()

        self.assertTrue(response['email_confirm'])
        self.assertEqual(self.smtp(0)['send_per_month'], 1000)
        self.assertEqual(self.smtp(1)['send_per_day'], day1 + 1)

    def test_with_every_provider_at_its_daily_limit_no_email_is_sent(self):
        self.reset_smtp_config()
        self.fill_all_providers(day=True)
        before = [self.counters(i) for i in range(len(self.local.local_settings['smtp_settings']))]

        response = self.create_booking()

        self.assertFalse(response['email_confirm'])
        self.assertEqual([self.counters(i) for i in range(len(before))], before)
        self.assertEmailFlag(response['booking']['id'], 'email_confirm', False)

    def test_a_provider_whose_daily_window_expired_is_usable_again_even_if_all_were_full(self):
        self.reset_smtp_config()
        self.fill_all_providers(day=True)
        self.set_smtp(0, reset_send_per_day=midnight(days=-1))

        response = self.create_booking()

        self.assertTrue(response['email_confirm'])
        self.assertEqual(self.smtp(0)['send_per_day'], 1)

    def test_a_provider_whose_monthly_window_expired_is_usable_again_even_if_all_were_full(self):
        self.reset_smtp_config()
        self.fill_all_providers(month=True)
        self.set_smtp(0, reset_send_per_month=midnight(days=-1))

        response = self.create_booking()

        self.assertTrue(response['email_confirm'])
        self.assertEqual(self.smtp(0)['send_per_month'], 1)

    def test_an_expired_daily_window_is_not_enough_when_the_month_is_also_full(self):
        self.reset_smtp_config()
        self.fill_all_providers(day=True, month=True)
        self.set_smtp(0, reset_send_per_day=midnight(days=-1))

        response = self.create_booking()

        self.assertFalse(response['email_confirm'])


class TestConfirmedEmail(EmailTestCase):
    """The customer confirms the booking from the link of the email."""

    def test_confirming_sends_the_confirmed_email_and_counts_it(self):
        response = self.create_booking()
        pre_day, pre_month = self.counters()

        r = self.confirm_booking(response['session_token'])

        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json['status']['status'], CONFIRMED_STATUS)
        self.assertCounters((pre_day + 1, pre_month + 1))
        self.assertEmailFlag(response['booking']['id'], 'email_confirmed', True)

    def test_a_booking_already_confirmed_cannot_be_confirmed_again(self):
        self.disable_send_email_confirm()
        response = self.create_booking()

        self.assertEqual(self.confirm_booking(response['session_token']).status_code, 409)

    def test_the_booking_is_readable_with_its_session_token(self):
        response = self.create_booking()

        r = self.get_booking(response['session_token'])

        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json['status']['status'], PENDING_STATUS)


class TestCancelledEmail(EmailTestCase):

    def test_cancelling_sends_the_cancelled_email_and_counts_it(self):
        response = self.create_booking()
        pre_day, pre_month = self.counters()

        r = self.cancel_booking(response['session_token'])

        self.assertEqual(r.status_code, 204)
        self.assertCounters((pre_day + 1, pre_month + 1))
        self.assertEmailFlag(response['booking']['id'], 'email_cancelled', True)

    def test_cancelling_with_confirmation_disabled_still_sends_the_cancelled_email(self):
        self.disable_send_email_confirm()
        response = self.create_booking()

        self.cancel_booking(response['session_token'])

        self.assertEqual(self.get_booking(response['session_token']).json['status']['status'], CANCELLED_STATUS)
        self.assertEmailFlag(response['booking']['id'], 'email_cancelled', True)

    def test_with_every_provider_at_its_limit_the_cancelled_email_is_not_sent(self):
        self.disable_send_email_confirm()
        self.reset_smtp_config(send_per_day=300, max_send_per_day=300)
        response = self.create_booking()

        self.cancel_booking(response['session_token'])

        self.assertEqual(self.get_booking(response['session_token']).json['status']['status'], CANCELLED_STATUS)
        self.assertEmailFlag(response['booking']['id'], 'email_cancelled', False)


class TestUpdatedEmail(EmailTestCase):

    def test_updating_sends_the_updated_email_and_counts_it(self):
        response = self.create_booking()
        pre_day, pre_month = self.counters()

        r = self.update_booking(response['session_token'], self.booking)

        self.assertEqual(r.status_code, 200)
        self.assertCounters((pre_day + 1, pre_month + 1))
        self.assertEmailFlag(response['booking']['id'], 'email_updated', True)


class TestConfirmationDisabledFlow(EmailTestCase):

    def setUp(self):
        super().setUp()
        self.disable_send_email_confirm()

    def test_the_confirmed_email_is_sent_when_the_booking_is_created(self):
        pre_day, pre_month = self.counters()

        response = self.create_booking()

        self.assertEqual(response['booking']['status']['status'], CONFIRMED_STATUS)
        self.assertEmailFlag(response['booking']['id'], 'email_confirm', False)
        self.assertEmailFlag(response['booking']['id'], 'email_confirmed', True)
        self.assertCounters((pre_day + 1, pre_month + 1))

    def test_at_the_limit_the_booking_is_confirmed_without_any_email(self):
        self.reset_smtp_config(send_per_day=300, max_send_per_day=300)

        response = self.create_booking()

        self.assertEqual(response['booking']['status']['status'], CONFIRMED_STATUS)
        self.assertFalse(response['email_confirm'])
        self.assertEmailFlag(response['booking']['id'], 'email_confirmed', False)


class TestNotificationsByTheLocal(EmailTestCase):
    """Bookings handled by the local only email the customer when notify=true."""

    def create_by_local(self, **params):
        r = self.post_booking_local(force=True, **params)
        self.assertEqual(r.status_code, 201, r.json)
        return r.json

    def test_creating_without_notify_sends_nothing(self):
        pre = self.counters()

        booking = self.create_by_local()

        self.assertCounters(pre)
        self.assertEmailFlag(booking['id'], 'email_confirm', False)
        self.assertEmailFlag(booking['id'], 'email_confirmed', False)

    def test_creating_with_notify_sends_the_confirmed_email(self):
        pre_day, pre_month = self.counters()

        booking = self.create_by_local(notify=True)

        self.assertCounters((pre_day + 1, pre_month + 1))
        self.assertEmailFlag(booking['id'], 'email_confirm', False)
        self.assertEmailFlag(booking['id'], 'email_confirmed', True)

    def update_body(self):
        return {**self.booking, 'new_status': 'C'}

    def test_updating_without_notify_sends_nothing(self):
        booking = self.create_by_local()
        pre = self.counters()

        r = self.update_booking_by_local(booking['id'], self.update_body(), force=True)

        self.assertEqual(r.status_code, 200)
        self.assertCounters(pre)
        self.assertEmailFlag(booking['id'], 'email_updated', False)

    def test_updating_with_notify_sends_the_updated_email(self):
        booking = self.create_by_local()
        pre_day, pre_month = self.counters()

        r = self.update_booking_by_local(booking['id'], self.update_body(), force=True, notify=True)

        self.assertEqual(r.status_code, 200)
        self.assertCounters((pre_day + 1, pre_month + 1))
        self.assertEmailFlag(booking['id'], 'email_updated', True)

    def test_cancelling_without_notify_sends_nothing(self):
        booking = self.create_by_local()
        pre = self.counters()

        r = self.cancel_booking_by_local(booking['id'])

        self.assertEqual(r.status_code, 204)
        self.assertCounters(pre)
        self.assertEmailFlag(booking['id'], 'email_cancelled', False)

    def test_cancelling_with_notify_sends_the_cancelled_email(self):
        booking = self.create_by_local()
        pre_day, pre_month = self.counters()

        r = self.cancel_booking_by_local(booking['id'], notify=True)

        self.assertEqual(r.status_code, 204)
        self.assertCounters((pre_day + 1, pre_month + 1))
        self.assertEmailFlag(booking['id'], 'email_cancelled', True)


class TestAutomaticCancellation(EmailTestCase):
    """A pending booking the customer never confirms is cancelled when check_booking_status runs."""

    def test_an_unconfirmed_booking_is_cancelled_and_the_customer_is_told(self):
        response = self.create_booking()

        check_booking_status(response['booking']['id'])

        self.assertEqual(self.get_booking(response['session_token']).json['status']['status'], CANCELLED_STATUS)
        self.assertEmailFlag(response['booking']['id'], 'email_cancelled', True)

    def test_a_confirmed_booking_is_left_alone(self):
        response = self.create_booking()
        self.assertEqual(self.confirm_booking(response['session_token']).status_code, 200)

        check_booking_status(response['booking']['id'])

        self.assertEqual(self.get_booking(response['session_token']).json['status']['status'], CONFIRMED_STATUS)
        self.assertEmailFlag(response['booking']['id'], 'email_confirmed', True)
        self.assertEmailFlag(response['booking']['id'], 'email_cancelled', False)

    def test_only_the_unconfirmed_one_of_two_bookings_is_cancelled(self):
        first = self.create_booking()
        self.booking['datetime_init'] = first['booking']['datetime_end']
        second = self.create_booking()
        self.confirm_booking(second['session_token'])

        check_booking_status(first['booking']['id'])
        check_booking_status(second['booking']['id'])

        self.assertEqual(self.get_booking(first['session_token']).json['status']['status'], CANCELLED_STATUS)
        self.assertEqual(self.get_booking(second['session_token']).json['status']['status'], CONFIRMED_STATUS)
        self.assertEmailFlag(first['booking']['id'], 'email_cancelled', True)
        self.assertEmailFlag(second['booking']['id'], 'email_confirmed', True)


class TestWaiterThread(EmailTestCase):
    """In test mode the app starts a thread that runs check_booking_status after BOOKING_TIMEOUT seconds.

    Only this class enables it, and it makes no assertion about SMTP counters (the thread changes them whenever it
    wants). It polls instead of sleeping a fixed time.
    """
    waiter = BOOKING_TIMEOUT

    def test_the_thread_cancels_a_booking_nobody_confirmed(self):
        response = self.create_booking()
        booking_id = response['booking']['id']

        deadline = time.time() + 20
        while time.time() < deadline:
            if self.get_booking_by_local(booking_id).json['email_cancelled']:
                break
            time.sleep(0.5)

        self.assertEqual(self.get_booking(response['session_token']).json['status']['status'], CANCELLED_STATUS)
        self.assertEmailFlag(booking_id, 'email_cancelled', True)
