import unittest
from datetime import datetime, timedelta

from dbbackup.scheduler import compute_due, dump_due
from tests.backup.helpers import TmpDirTestCase


def at(h, m=0, day=7):
    return datetime(2026, 11, day, h, m, 0)


class TestDumpDue(TmpDirTestCase):
    def test_not_due_before_scheduled_time_if_a_dump_exists(self):
        self.state.set_dt('last_dump_ok', at(4, 0, day=6))
        self.assertFalse(dump_due(self.cfg, self.state, at(3, 59)))

    def test_first_ever_run_dumps_immediately_even_before_schedule(self):
        self.assertTrue(dump_due(self.cfg, self.state, at(1, 0)))

    def test_due_at_scheduled_time(self):
        self.state.set_dt('last_dump_ok', at(4, 0, day=6))
        self.assertTrue(dump_due(self.cfg, self.state, at(4, 0)))

    def test_not_due_again_after_todays_success(self):
        self.state.set_dt('last_dump_ok', at(4, 1))
        self.assertFalse(dump_due(self.cfg, self.state, at(15, 0)))

    def test_catches_up_when_container_was_down_at_4am(self):
        self.state.set_dt('last_dump_ok', at(4, 0, day=6))
        self.assertTrue(dump_due(self.cfg, self.state, at(9, 30)))

    def test_failed_attempt_is_retried_only_after_the_retry_interval(self):
        self.state.set_dt('last_dump_ok', at(4, 0, day=6))
        self.state.set_dt('last_dump_attempt', at(4, 0))
        self.assertFalse(dump_due(self.cfg, self.state, at(4, 29)))
        self.assertTrue(dump_due(self.cfg, self.state, at(4, 30)))

    def test_custom_schedule(self):
        cfg = self.cfg.__class__(**{**self.cfg.__dict__, 'dump_hour': 2, 'dump_minute': 15})
        self.state.set_dt('last_dump_ok', at(2, 15, day=6))
        self.assertFalse(dump_due(cfg, self.state, at(2, 14)))
        self.assertTrue(dump_due(cfg, self.state, at(2, 15)))


class TestComputeDue(TmpDirTestCase):
    def test_binlogs_due_every_interval(self):
        now = at(12, 0)
        self.state.set_dt('last_binlog_ship', now - timedelta(hours=5, minutes=59))
        self.assertFalse(compute_due(self.cfg, self.state, now, 0).binlogs)
        self.state.set_dt('last_binlog_ship', now - timedelta(hours=6))
        self.assertTrue(compute_due(self.cfg, self.state, now, 0).binlogs)

    def test_binlog_failure_does_not_retry_every_tick(self):
        now = at(12, 0)
        self.state.set_dt('last_binlog_ship', now - timedelta(hours=7))
        self.state.set_dt('last_binlog_attempt', now - timedelta(minutes=1))
        self.assertFalse(compute_due(self.cfg, self.state, now, 0).binlogs)
        self.state.set_dt('last_binlog_attempt', now - timedelta(minutes=31))
        self.assertTrue(compute_due(self.cfg, self.state, now, 0).binlogs)

    def test_send_needs_pending_items_and_retry_interval(self):
        now = at(12, 0)
        self.assertFalse(compute_due(self.cfg, self.state, now, 0).send)
        self.assertTrue(compute_due(self.cfg, self.state, now, 2).send)
        self.state.set_dt('last_send_attempt', now - timedelta(minutes=5))
        self.assertFalse(compute_due(self.cfg, self.state, now, 2).send)
        self.state.set_dt('last_send_attempt', now - timedelta(minutes=15))
        self.assertTrue(compute_due(self.cfg, self.state, now, 2).send)

    def test_send_never_due_without_remote(self):
        cfg = self.cfg.__class__(**{**self.cfg.__dict__, 'remote_host': ''})
        self.assertFalse(compute_due(cfg, self.state, at(12), 5).send)

    def test_heartbeat_interval(self):
        now = at(12, 0)
        self.assertTrue(compute_due(self.cfg, self.state, now, 0).heartbeat)
        self.state.set_dt('last_heartbeat', now - timedelta(minutes=4))
        self.assertFalse(compute_due(self.cfg, self.state, now, 0).heartbeat)
        self.state.set_dt('last_heartbeat', now - timedelta(minutes=5))
        self.assertTrue(compute_due(self.cfg, self.state, now, 0).heartbeat)


if __name__ == '__main__':
    unittest.main()
