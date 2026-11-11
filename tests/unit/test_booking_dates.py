"""Date arithmetic of bookings and the timezone helpers (no DB)."""
import datetime
import unittest
from types import SimpleNamespace
from unittest import mock

import pytz

from helpers import BookingController, DatetimeHelper
from helpers.BookingController import calculatEndTimeBooking, calculateExpireBookingToken

MADRID = pytz.timezone('Europe/Madrid')


def booking(init, *durations):
    return SimpleNamespace(datetime_init=init, datetime_end=None, services=[SimpleNamespace(duration=d) for d in durations])


class TestCalculateEndTimeBooking(unittest.TestCase):
    INIT = datetime.datetime(2030, 1, 1, 10, 0)

    def test_end_is_init_plus_the_sum_of_the_service_durations(self):
        result = calculatEndTimeBooking(booking(self.INIT, 30, 45))

        self.assertEqual(result.datetime_end, datetime.datetime(2030, 1, 1, 11, 15))

    def test_single_service(self):
        self.assertEqual(calculatEndTimeBooking(booking(self.INIT, 60)).datetime_end, datetime.datetime(2030, 1, 1, 11, 0))

    def test_no_services_ends_when_it_starts(self):
        self.assertEqual(calculatEndTimeBooking(booking(self.INIT)).datetime_end, self.INIT)

    def test_crosses_midnight(self):
        result = calculatEndTimeBooking(booking(datetime.datetime(2030, 1, 1, 23, 30), 60))

        self.assertEqual(result.datetime_end, datetime.datetime(2030, 1, 2, 0, 30))

    def test_returns_the_same_booking_object(self):
        b = booking(self.INIT, 30)

        self.assertIs(calculatEndTimeBooking(b), b)


class TestCalculateExpireBookingToken(unittest.TestCase):
    """Token lifetime = time left until the booking ends."""

    def at(self, year, month, day, hour, minute=0):
        return MADRID.localize(datetime.datetime(year, month, day, hour, minute))

    def expire(self, end, current):
        with mock.patch.object(BookingController, 'now', return_value=current):
            return calculateExpireBookingToken(end, 'Europe/Madrid')

    def test_remaining_time_until_the_booking_ends(self):
        diff = self.expire(datetime.datetime(2030, 1, 2, 12, 0), self.at(2030, 1, 1, 10))

        self.assertEqual(diff, datetime.timedelta(days=1, hours=2))

    def test_negative_when_the_booking_already_ended(self):
        diff = self.expire(datetime.datetime(2030, 1, 1, 9, 0), self.at(2030, 1, 1, 10))

        self.assertEqual(diff, datetime.timedelta(hours=-1))

    def test_zero_when_it_ends_right_now(self):
        self.assertEqual(self.expire(datetime.datetime(2030, 1, 1, 10, 0), self.at(2030, 1, 1, 10)), datetime.timedelta(0))

    def test_across_the_spring_dst_change_counts_real_elapsed_time(self):
        # Madrid clocks go forward on 2030-03-31 02:00: from 2030-03-30 22:00 to 2030-03-31 04:00 are 5 real hours
        diff = self.expire(datetime.datetime(2030, 3, 31, 4, 0), self.at(2030, 3, 30, 22))

        self.assertEqual(diff, datetime.timedelta(hours=5))

    def test_uses_the_requested_location_for_the_current_time(self):
        with mock.patch.object(BookingController, 'now', return_value=self.at(2030, 1, 1, 10)) as now:
            calculateExpireBookingToken(datetime.datetime(2030, 1, 2), 'Europe/Madrid')

        now.assert_called_with('Europe/Madrid')


class TestDatetimeHelper(unittest.TestCase):

    def test_now_is_timezone_aware_in_the_requested_zone(self):
        current = DatetimeHelper.now('Asia/Tokyo')

        self.assertTrue(DatetimeHelper.isAware(current))
        self.assertEqual(current.utcoffset(), datetime.timedelta(hours=9))

    def test_now_defaults_to_madrid(self):
        self.assertIn(DatetimeHelper.now().utcoffset(), (datetime.timedelta(hours=1), datetime.timedelta(hours=2)))

    def test_now_rejects_an_unknown_zone(self):
        with self.assertRaises(pytz.UnknownTimeZoneError):
            DatetimeHelper.now('Mars/Olympus')

    def test_naive_to_aware_uses_winter_offset(self):
        result = DatetimeHelper.naiveToAware(datetime.datetime(2030, 1, 15, 12, 0))

        self.assertEqual(result.utcoffset(), datetime.timedelta(hours=1))
        self.assertEqual(result.hour, 12)

    def test_naive_to_aware_uses_summer_offset(self):
        result = DatetimeHelper.naiveToAware(datetime.datetime(2030, 7, 15, 12, 0))

        self.assertEqual(result.utcoffset(), datetime.timedelta(hours=2))

    def test_naive_to_aware_with_another_zone(self):
        result = DatetimeHelper.naiveToAware(datetime.datetime(2030, 1, 15, 12, 0), 'UTC')

        self.assertEqual(result.utcoffset(), datetime.timedelta(0))

    def test_is_aware(self):
        self.assertFalse(DatetimeHelper.isAware(datetime.datetime(2030, 1, 1)))
        self.assertTrue(DatetimeHelper.isAware(datetime.datetime(2030, 1, 1, tzinfo=datetime.timezone.utc)))

    def test_datetime_now_marker_is_the_documented_sentinel(self):
        self.assertEqual(DatetimeHelper.DATETIME_NOW, -1)


if __name__ == '__main__':
    unittest.main()
