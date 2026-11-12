import datetime
import json
import uuid
from unittest import mock

from celery.exceptions import Retry

from flask_testing import TestCase

from app import create_app, db
from celery_app import tasks
from celery_app.tasks import send_mail_task
from globals import EmailType
from helpers.error.BookingError.BookingNotFoundException import BookingNotFoundException
from helpers.error.LocalError.LocalNotFoundException import LocalNotFoundException
from models.booking import BookingModel
from tests.config_test import config_test, getUrl
from tests.configure_local_base import configure

CONFIRMED = int(EmailType.CONFIRMED_EMAIL)
CANCELLED = int(EmailType.CANCELLED_EMAIL)
UPDATED = int(EmailType.UPDATED_EMAIL)


class SendMailTaskTestCase(TestCase):
    full_local = True
    set_local_settings = True

    def create_app(self):
        app = create_app(config_test)
        self.locals = []
        return app

    def setUp(self):
        db.create_all()
        config_test.config(db=db)
        full = self.full_local
        self.local = configure(self.client, config_test.ADMIN_TOKEN, self.assertEqual, -1,
                               set_local_settings=self.set_local_settings, set_smtp_settings=self.set_local_settings,
                               set_timetable=full, set_work_groups=full, set_services=full, set_workers=full)
        self.locals = self.local.locals
        self.local_id = self.local.local['id']
        self.booking_id = self.create_booking() if full else None

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        config_test.drop(self.locals)

    def create_booking(self):
        opening = self.local.timetable[0]['opening_time']
        day = (datetime.datetime.now() + datetime.timedelta(days=1)).strftime('%Y-%m-%d')
        data = {
            'client_name': 'Client Test',
            'client_tlf': '123456789',
            'client_email': 'client@example.com',
            'datetime_init': f'{day} {opening}',
            'services_ids': [self.local.services[0]['id']],
        }
        r = self.client.post(getUrl('booking', 'local', self.local_id), data=json.dumps(data), content_type='application/json')
        self.assertEqual(r.status_code, 201)
        return r.json['booking']['id']

    def run_task(self, local_id=None, booking_id=None, email_type=CONFIRMED):
        return send_mail_task.apply(args=(local_id or self.local_id, booking_id or self.booking_id, email_type))

    def booking(self):
        db.session.expire_all()
        return BookingModel.query.get(self.booking_id)


class TestSendMailTask(SendMailTaskTestCase):

    def test_success_marks_confirmed_email_as_sent(self):
        with mock.patch.object(tasks, 'send_confirmed_booking_mail', return_value=True) as sender:
            result = self.run_task()

        self.assertTrue(result.successful())
        sender.assert_called_once()
        self.assertTrue(self.booking().email_confirmed)

    def test_a_redelivered_copy_of_the_same_task_does_not_send_the_email_twice(self):
        task_id = uuid.uuid4().hex
        with mock.patch.object(tasks, 'send_confirmed_booking_mail', return_value=True) as sender:
            first = send_mail_task.apply(args=(self.local_id, self.booking_id, CONFIRMED), task_id=task_id)
            second = send_mail_task.apply(args=(self.local_id, self.booking_id, CONFIRMED), task_id=task_id)

        self.assertTrue(first.successful())
        self.assertTrue(second.successful())
        self.assertEqual(sender.call_count, 1)

    def test_a_copy_of_the_same_task_that_is_sending_right_now_makes_this_one_skip(self):
        task_id = uuid.uuid4().hex
        tasks.set_key_if_absent(tasks.email_sent_key(task_id) + ':claim', 1, exp=60)  # the other copy's claim
        with mock.patch.object(tasks, 'send_confirmed_booking_mail', return_value=True) as sender:
            result = send_mail_task.apply(args=(self.local_id, self.booking_id, CONFIRMED), task_id=task_id)

        self.assertTrue(result.successful())
        sender.assert_not_called()

    def test_the_claim_is_released_when_the_task_ends_so_a_later_redelivery_can_send(self):
        task_id = uuid.uuid4().hex
        with mock.patch.object(tasks, 'send_confirmed_booking_mail', return_value=False),                 mock.patch.object(tasks, 'is_email_test_mode', return_value=True):
            send_mail_task.apply(args=(self.local_id, self.booking_id, CONFIRMED), task_id=task_id)

        self.assertTrue(tasks.set_key_if_absent(tasks.email_sent_key(task_id) + ':claim', 1, exp=60))

    def test_two_copies_of_the_same_failed_attempt_schedule_a_single_retry(self):
        task_id = uuid.uuid4().hex
        with mock.patch.object(tasks, 'send_confirmed_booking_mail', return_value=False) as sender,                 mock.patch.object(tasks, 'is_email_test_mode', return_value=False),                 mock.patch.object(send_mail_task, 'retry', side_effect=Retry()) as retry:
            send_mail_task.apply(args=(self.local_id, self.booking_id, CONFIRMED), task_id=task_id, retries=0)
            send_mail_task.apply(args=(self.local_id, self.booking_id, CONFIRMED), task_id=task_id, retries=0)

        self.assertEqual(sender.call_count, 1)
        self.assertEqual(retry.call_count, 1)

    def test_the_next_attempt_of_the_same_task_is_not_blocked_by_the_previous_one(self):
        task_id = uuid.uuid4().hex
        with mock.patch.object(tasks, 'send_confirmed_booking_mail', return_value=False) as sender,                 mock.patch.object(tasks, 'is_email_test_mode', return_value=False),                 mock.patch.object(send_mail_task, 'retry', side_effect=Retry()):
            send_mail_task.apply(args=(self.local_id, self.booking_id, CONFIRMED), task_id=task_id, retries=0)
            send_mail_task.apply(args=(self.local_id, self.booking_id, CONFIRMED), task_id=task_id, retries=1)

        self.assertEqual(sender.call_count, 2)

    def test_a_new_request_for_the_same_booking_and_type_still_sends(self):
        with mock.patch.object(tasks, 'send_updated_booking_mail', return_value=True) as sender:
            send_mail_task.apply(args=(self.local_id, self.booking_id, UPDATED), task_id=uuid.uuid4().hex)
            send_mail_task.apply(args=(self.local_id, self.booking_id, UPDATED), task_id=uuid.uuid4().hex)

        self.assertEqual(sender.call_count, 2)

    def test_a_failed_send_is_not_remembered_so_the_retry_sends_again(self):
        task_id = uuid.uuid4().hex
        with mock.patch.object(tasks, 'send_confirmed_booking_mail', return_value=False) as sender,                 mock.patch.object(tasks, 'is_email_test_mode', return_value=False):
            send_mail_task.apply(args=(self.local_id, self.booking_id, CONFIRMED), task_id=task_id)

        self.assertGreater(sender.call_count, 1)

    def test_if_redis_fails_the_email_is_sent_anyway(self):
        with mock.patch.object(tasks, 'get_key_value_cache', side_effect=ConnectionError('redis down')),                 mock.patch.object(tasks, 'send_confirmed_booking_mail', return_value=True) as sender:
            result = self.run_task()

        self.assertTrue(result.successful())
        sender.assert_called_once()

    def test_success_marks_cancelled_email_as_sent(self):
        with mock.patch.object(tasks, 'send_cancelled_booking_mail', return_value=True):
            self.assertTrue(self.run_task(email_type=CANCELLED).successful())

        self.assertTrue(self.booking().email_cancelled)

    def test_success_marks_updated_email_as_sent(self):
        with mock.patch.object(tasks, 'send_updated_booking_mail', return_value=True):
            self.assertTrue(self.run_task(email_type=UPDATED).successful())

        self.assertTrue(self.booking().email_updated)

    def test_success_only_touches_its_own_flag(self):
        with mock.patch.object(tasks, 'send_confirmed_booking_mail', return_value=True):
            self.run_task()

        booking = self.booking()
        self.assertFalse(booking.email_cancelled)
        self.assertFalse(booking.email_updated)

    def test_unknown_email_type_fails_without_retrying(self):
        with mock.patch.object(tasks, 'send_confirmed_booking_mail') as sender:
            result = self.run_task(email_type=9999)

        self.assertTrue(result.failed())
        sender.assert_not_called()

    def test_failed_send_in_email_test_mode_does_not_retry(self):
        with mock.patch.object(tasks, 'send_confirmed_booking_mail', return_value=False) as sender, \
                mock.patch.object(tasks, 'is_email_test_mode', return_value=True):
            result = self.run_task()

        self.assertTrue(result.successful())
        self.assertEqual(sender.call_count, 1)
        self.assertFalse(self.booking().email_confirmed)

    def test_failed_send_retries_up_to_max_retries_then_fails(self):
        with mock.patch.object(tasks, 'send_confirmed_booking_mail', return_value=False) as sender, \
                mock.patch.object(tasks, 'is_email_test_mode', return_value=False):
            result = self.run_task()

        self.assertTrue(result.failed())
        self.assertEqual(sender.call_count, send_mail_task.max_retries + 1)
        self.assertEqual(send_mail_task.max_retries, 12)
        self.assertFalse(self.booking().email_confirmed)

    def test_exception_while_sending_is_retried(self):
        with mock.patch.object(tasks, 'send_confirmed_booking_mail', side_effect=[RuntimeError('smtp down'), True]) as sender:
            result = self.run_task()

        self.assertTrue(result.successful())
        self.assertEqual(sender.call_count, 2)
        self.assertTrue(self.booking().email_confirmed)

    def test_persistent_exception_exhausts_retries_with_original_error(self):
        with mock.patch.object(tasks, 'send_confirmed_booking_mail', side_effect=RuntimeError('smtp down')) as sender:
            result = self.run_task()

        self.assertTrue(result.failed())
        self.assertIsInstance(result.result, RuntimeError)
        self.assertEqual(sender.call_count, send_mail_task.max_retries + 1)

    def test_missing_booking_raises_not_found_without_sending(self):
        with mock.patch.object(tasks, 'send_confirmed_booking_mail') as sender:
            result = self.run_task(booking_id=999999)

        self.assertTrue(result.failed())
        self.assertIsInstance(result.result, BookingNotFoundException)
        sender.assert_not_called()

    def test_missing_local_raises_not_found_without_sending(self):
        with mock.patch.object(tasks, 'send_confirmed_booking_mail') as sender:
            result = self.run_task(local_id='0' * 32)

        self.assertTrue(result.failed())
        self.assertIsInstance(result.result, LocalNotFoundException)
        sender.assert_not_called()

    def test_retry_delay_is_configured(self):
        self.assertEqual(send_mail_task.default_retry_delay, 60 * tasks.RETRY_SEND_EMAIL)

    def test_task_is_routed_to_priority_queue(self):
        self.assertEqual(send_mail_task.queue, 'priority')


class TestSendMailTaskWithoutLocalSettings(SendMailTaskTestCase):
    full_local = False
    set_local_settings = False

    def test_local_without_settings_returns_without_sending(self):
        with mock.patch.object(tasks, 'send_confirmed_booking_mail') as sender:
            result = send_mail_task.apply(args=(self.local_id, 1, CONFIRMED))

        self.assertTrue(result.successful())
        sender.assert_not_called()
