import unittest
from unittest import mock

import fakeredis
import redis

from helpers import BookingController
from helpers.BookingController import perform_atomic_booking, waitAndRegisterBooking
from helpers.error.LocalError.LocalOverloadedException import LocalOverloadedException

LOCAL_ID = 'local-1'
DATE = '2030-01-01 10:00:00'


class AtomicBookingTestCase(unittest.TestCase):

    def setUp(self):
        self.server = fakeredis.FakeServer()
        self.client = fakeredis.FakeStrictRedis(server=self.server)
        self.other_client = fakeredis.FakeStrictRedis(server=self.server)


class TestPerformAtomicBooking(AtomicBookingTestCase):

    def test_first_booking_is_registered_with_ttl(self):
        self.assertTrue(perform_atomic_booking(self.client, LOCAL_ID, DATE, exp=30))

        self.assertEqual(self.client.get(LOCAL_ID).decode(), DATE)
        self.assertTrue(0 < self.client.ttl(LOCAL_ID) <= 30)

    def test_same_date_is_rejected_and_value_is_untouched(self):
        self.client.set(LOCAL_ID, DATE)

        self.assertFalse(perform_atomic_booking(self.client, LOCAL_ID, DATE))

        self.assertEqual(self.client.get(LOCAL_ID).decode(), DATE)

    def test_different_date_is_appended(self):
        self.client.set(LOCAL_ID, DATE)

        self.assertTrue(perform_atomic_booking(self.client, LOCAL_ID, '2030-01-01 11:00:00'))

        self.assertEqual(self.client.get(LOCAL_ID).decode(), f'{DATE}|2030-01-01 11:00:00')

    def test_locals_do_not_share_locks(self):
        self.assertTrue(perform_atomic_booking(self.client, 'local-a', DATE))
        self.assertTrue(perform_atomic_booking(self.client, 'local-b', DATE))

    def test_concurrent_writer_between_watch_and_exec_returns_false(self):
        # Another process writes the watched key after our GET and before EXEC.
        # The real WATCH semantics must abort the transaction instead of overwriting.
        interfered = []

        def interfere(message, *args, **kwargs):
            if not interfered and str(message).startswith('Current value'):
                interfered.append(True)
                self.other_client.set(LOCAL_ID, 'booked-by-someone-else')

        with mock.patch.object(BookingController, 'log', side_effect=interfere):
            result = perform_atomic_booking(self.client, LOCAL_ID, DATE)

        self.assertTrue(interfered)
        self.assertFalse(result)
        self.assertEqual(self.client.get(LOCAL_ID).decode(), 'booked-by-someone-else')


@mock.patch.object(BookingController, 'is_redis_test_mode', return_value=False)
class TestWaitAndRegisterBooking(AtomicBookingTestCase):

    def test_returns_none_without_touching_redis_in_test_mode(self, test_mode):
        test_mode.return_value = True

        with mock.patch.object(BookingController, 'create_redis_connection') as create:
            self.assertIsNone(waitAndRegisterBooking(LOCAL_ID, DATE))

        create.assert_not_called()

    def test_registers_on_first_try(self, _):
        with mock.patch.object(BookingController, 'create_redis_connection', return_value=self.client):
            uuid = waitAndRegisterBooking(LOCAL_ID, DATE, uuid='u-1')

        self.assertEqual(uuid, 'u-1')
        self.assertEqual(self.client.get(LOCAL_ID).decode(), DATE)

    def test_retries_until_the_slot_frees_up(self, _):
        with mock.patch.object(BookingController, 'create_redis_connection', return_value=self.client), \
                mock.patch.object(BookingController, 'perform_atomic_booking', side_effect=[False, False, True]) as atomic, \
                mock.patch.object(BookingController.time, 'sleep') as sleep:
            waitAndRegisterBooking(LOCAL_ID, DATE, uuid='u-1')

        self.assertEqual(atomic.call_count, 3)
        self.assertEqual(sleep.call_count, 2)

    def test_raises_local_overloaded_after_timeout(self, _):
        with mock.patch.object(BookingController, 'create_redis_connection', return_value=self.client), \
                mock.patch.object(BookingController, 'perform_atomic_booking', return_value=False):
            with self.assertRaises(LocalOverloadedException):
                waitAndRegisterBooking(LOCAL_ID, DATE, max_timeout=1, sleep_time=0.05)

    def test_reconnects_after_redis_connection_error(self, _):
        with mock.patch.object(BookingController, 'create_redis_connection', return_value=self.client) as create, \
                mock.patch.object(BookingController, 'perform_atomic_booking', side_effect=[redis.ConnectionError('down'), True]), \
                mock.patch.object(BookingController.time, 'sleep'):
            waitAndRegisterBooking(LOCAL_ID, DATE, uuid='u-1')

        self.assertEqual(create.call_count, 2)

    def test_second_caller_for_same_slot_is_blocked_until_timeout(self, _):
        with mock.patch.object(BookingController, 'create_redis_connection', return_value=self.client):
            waitAndRegisterBooking(LOCAL_ID, DATE, uuid='first')

            with self.assertRaises(LocalOverloadedException):
                waitAndRegisterBooking(LOCAL_ID, DATE, max_timeout=1, sleep_time=0.05, uuid='second')


if __name__ == '__main__':
    unittest.main()
