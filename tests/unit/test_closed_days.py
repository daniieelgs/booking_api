"""helpers/closed.py: closing-day lookup (real SQLite) and the overlap rules."""
import datetime

from db import db
from helpers.closed import checkClosedDay, getClosedDays
from helpers.error.ClosedDaysError.BadDatetimesClosedDaysException import BadDatetimesClosedDaysException
from helpers.error.ClosedDaysError.ConflictClosedDaysException import ConflictClosedDaysException
from models.closed import ClosedModel
from tests.unit.db_support import DbTestCase

LOCAL = 'local-1'
FUTURE = datetime.datetime.now() + datetime.timedelta(days=365)


def day(offset_days, hours=0):
    return FUTURE + datetime.timedelta(days=offset_days, hours=hours)


def closed_range(init, end, local=LOCAL, id=None):
    model = ClosedModel(datetime_init=init, datetime_end=end, local_id=local, id=id)
    db.session.add(model)
    db.session.commit()
    return model


class TestGetClosedDays(DbTestCase):

    def test_returns_only_the_days_of_that_local(self):
        mine = closed_range(day(1), day(2))
        closed_range(day(1), day(2), local='other')

        self.assertEqual([c.id for c in getClosedDays(LOCAL)], [mine.id])

    def test_empty_when_the_local_has_none(self):
        self.assertEqual(getClosedDays(LOCAL), [])

    def test_filters_by_datetime_init(self):
        closed_range(day(1), day(2))
        later = closed_range(day(10), day(11))

        result = getClosedDays(LOCAL, datetime_init=day(5))

        self.assertEqual([c.id for c in result], [later.id])

    def test_filters_by_datetime_end(self):
        early = closed_range(day(1), day(2))
        closed_range(day(10), day(11))

        result = getClosedDays(LOCAL, datetime_end=day(5))

        self.assertEqual([c.id for c in result], [early.id])

    def test_range_touching_the_window_is_included(self):
        inside = closed_range(day(1), day(3))

        result = getClosedDays(LOCAL, datetime_init=day(3), datetime_end=day(4))

        self.assertEqual([c.id for c in result], [inside.id])

    def test_expired_closing_days_are_deleted(self):
        closed_range(datetime.datetime(2000, 1, 1), datetime.datetime(2000, 1, 2))
        alive = closed_range(day(1), day(2))

        result = getClosedDays(LOCAL)

        self.assertEqual([c.id for c in result], [alive.id])
        self.assertEqual(ClosedModel.query.count(), 1)

    def test_all_expired_closing_days_are_deleted_not_only_alternate_ones(self):
        # the loop removes items from the list it is iterating, which skips the element after each removal
        for year in (2000, 2001, 2002, 2003):
            closed_range(datetime.datetime(year, 1, 1), datetime.datetime(year, 1, 2))
        alive = closed_range(day(1), day(2))

        result = getClosedDays(LOCAL)

        self.assertEqual([c.id for c in result], [alive.id])
        self.assertEqual(ClosedModel.query.count(), 1)


class TestCheckClosedDay(DbTestCase):

    def existing(self):
        return [closed_range(day(10), day(12), id=1)]

    def test_rejects_init_equal_to_end(self):
        with self.assertRaises(BadDatetimesClosedDaysException):
            checkClosedDay(LOCAL, day(1), day(1))

    def test_rejects_init_after_end(self):
        with self.assertRaises(BadDatetimesClosedDaysException):
            checkClosedDay(LOCAL, day(2), day(1))

    def test_valid_when_there_is_nothing_else(self):
        self.assertTrue(checkClosedDay(LOCAL, day(1), day(2)))

    def test_valid_when_clearly_apart(self):
        self.existing()

        self.assertTrue(checkClosedDay(LOCAL, day(1), day(5)))

    def test_conflict_when_the_start_falls_inside_another(self):
        self.existing()

        with self.assertRaises(ConflictClosedDaysException):
            checkClosedDay(LOCAL, day(11), day(14))

    def test_conflict_when_the_end_falls_inside_another(self):
        self.existing()

        with self.assertRaises(ConflictClosedDaysException):
            checkClosedDay(LOCAL, day(8), day(11))

    def test_conflict_when_inside_another(self):
        self.existing()

        with self.assertRaises(ConflictClosedDaysException):
            checkClosedDay(LOCAL, day(10, 1), day(10, 2))

    def test_conflict_when_it_contains_another_entirely(self):
        self.existing()

        with self.assertRaises(ConflictClosedDaysException):
            checkClosedDay(LOCAL, day(9), day(13))

    def test_back_to_back_ranges_do_not_conflict(self):
        self.existing()

        self.assertTrue(checkClosedDay(LOCAL, day(12), day(14)))
        self.assertTrue(checkClosedDay(LOCAL, day(8), day(10)))

    def test_a_range_can_be_updated_over_itself(self):
        self.existing()

        self.assertTrue(checkClosedDay(LOCAL, day(10, 1), day(11), closedDayId=1))

    def test_other_locals_do_not_conflict(self):
        closed_range(day(10), day(12), local='other')

        self.assertTrue(checkClosedDay(LOCAL, day(10), day(12)))
