"""helpers/TimetableController.py against a real SQLite."""
import datetime

from db import db
from helpers.TimetableController import getTimetable, validateTimetable
from helpers.error.TimetableError.TimetableOverlapsException import TimetableOverlapsException
from helpers.error.TimetableError.TimetableTimesException import TimetableTimesException
from models.timetable import TimetableModel
from tests.unit.db_support import DbTestCase

LOCAL = 'local-1'
MONDAY, TUESDAY = 1, 2


def t(hour, minute=0):
    return datetime.time(hour, minute)


def add(opening, closing, weekday=MONDAY, local=LOCAL):
    model = TimetableModel(opening_time=opening, closing_time=closing, weekday_id=weekday, local_id=local)
    db.session.add(model)
    db.session.commit()
    return model


class TestGetTimetable(DbTestCase):

    def test_returns_only_that_local_ordered_by_weekday_and_opening(self):
        late = add(t(16), t(20), MONDAY)
        early = add(t(9), t(13), MONDAY)
        tuesday = add(t(9), t(13), TUESDAY)
        add(t(9), t(13), MONDAY, local='other')

        self.assertEqual([x.id for x in getTimetable(LOCAL)], [early.id, late.id, tuesday.id])

    def test_filters_by_weekday(self):
        add(t(9), t(13), MONDAY)
        tuesday = add(t(9), t(13), TUESDAY)

        self.assertEqual([x.id for x in getTimetable(LOCAL, weekday_id=TUESDAY)], [tuesday.id])

    def test_empty_when_the_local_has_no_timetable(self):
        self.assertEqual(getTimetable(LOCAL), [])

    def test_keeps_only_slots_that_contain_the_booking(self):
        morning = add(t(9), t(13))
        add(t(16), t(20))

        result = getTimetable(LOCAL, MONDAY, datetime.datetime(2030, 1, 7, 10), datetime.datetime(2030, 1, 7, 11))

        self.assertEqual([x.id for x in result], [morning.id])

    def test_booking_ending_exactly_at_closing_time_fits(self):
        morning = add(t(9), t(13))

        result = getTimetable(LOCAL, MONDAY, datetime.datetime(2030, 1, 7, 12), datetime.datetime(2030, 1, 7, 13))

        self.assertEqual([x.id for x in result], [morning.id])

    def test_booking_starting_before_opening_does_not_fit(self):
        add(t(9), t(13))

        self.assertEqual(getTimetable(LOCAL, MONDAY, datetime.datetime(2030, 1, 7, 8, 30), datetime.datetime(2030, 1, 7, 9, 30)), [])

    def test_booking_in_the_gap_between_slots_does_not_fit(self):
        add(t(9), t(13))
        add(t(16), t(20))

        self.assertEqual(getTimetable(LOCAL, MONDAY, datetime.datetime(2030, 1, 7, 13), datetime.datetime(2030, 1, 7, 14)), [])


class TestValidateTimetable(DbTestCase):

    def test_valid_split_day(self):
        add(t(9), t(13))
        add(t(16), t(20))

        self.assertTrue(validateTimetable(LOCAL))

    def test_valid_when_there_is_no_timetable(self):
        self.assertTrue(validateTimetable(LOCAL))

    def test_same_hours_on_different_days_are_fine(self):
        add(t(9), t(13), MONDAY)
        add(t(9), t(13), TUESDAY)

        self.assertTrue(validateTimetable(LOCAL))

    def test_same_hours_in_another_local_are_fine(self):
        add(t(9), t(13), MONDAY, local='other')
        add(t(9), t(13), MONDAY)

        self.assertTrue(validateTimetable(LOCAL))

    def test_opening_after_closing_is_rejected(self):
        add(t(14), t(9))

        with self.assertRaises(TimetableTimesException):
            validateTimetable(LOCAL)

    def test_opening_equal_to_closing_is_rejected(self):
        add(t(9), t(9))

        with self.assertRaises(TimetableTimesException):
            validateTimetable(LOCAL)

    def test_partially_overlapping_slots_are_rejected(self):
        add(t(9), t(14))
        add(t(13), t(18))

        with self.assertRaises(TimetableOverlapsException):
            validateTimetable(LOCAL)

    def test_identical_slots_are_rejected(self):
        add(t(9), t(13))
        add(t(9), t(13))

        with self.assertRaises(TimetableOverlapsException):
            validateTimetable(LOCAL)

    def test_a_slot_inside_another_is_rejected(self):
        add(t(9), t(18))
        add(t(10), t(12))

        with self.assertRaises(TimetableOverlapsException):
            validateTimetable(LOCAL)
