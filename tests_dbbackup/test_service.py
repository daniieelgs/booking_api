import unittest
from datetime import datetime, timedelta
from unittest import mock

from dbbackup import service, transfer
from dbbackup.transfer import SendResult
from dbbackup.util import CommandError
from tests_dbbackup.helpers import FAKE_DUMP, TmpDirTestCase

AT_4AM = datetime(2026, 11, 7, 4, 0, 5)


class ServiceTestCase(TmpDirTestCase):
    def setUp(self):
        super().setUp()
        self.patches = {}
        for name, target in {
            'make_dump': 'dbbackup.service.dump.make_dump',
            'flush': 'dbbackup.service.binlogs.flush_binary_logs',
            'archive': 'dbbackup.service.binlogs.archive_new_binlogs',
            'send': 'dbbackup.service.transfer.send_pending',
            'kuma': 'dbbackup.service.heartbeat.push_kuma',
        }.items():
            p = mock.patch(target)
            self.patches[name] = p.start()
            self.addCleanup(p.stop)
        self.patches['make_dump'].return_value = {'name': 'dump-x'}
        self.patches['archive'].return_value = []
        self.patches['send'].return_value = SendResult()


class TestRunCycle(ServiceTestCase):
    def test_nightly_dump_then_archive_then_send(self):
        self.state.set_dt('last_dump_ok', AT_4AM - timedelta(days=1))
        self.state.set_dt('last_binlog_ship', AT_4AM - timedelta(hours=1))  # binlogs not due on their own
        summary = service.run_cycle(self.cfg, self.state, AT_4AM)
        self.patches['make_dump'].assert_called_once()
        self.patches['flush'].assert_called_once()   # a dump forces a binlog archive right after
        self.patches['archive'].assert_called_once()
        self.patches['send'].assert_called_once()
        self.assertEqual(summary['errors'], [])
        self.assertEqual(self.state.get_dt('last_dump_ok'), AT_4AM.replace(microsecond=0))

    def test_nothing_due_does_nothing(self):
        self.state.set_dt('last_dump_ok', AT_4AM)
        self.state.set_dt('last_binlog_ship', AT_4AM)
        self.state.set_dt('last_heartbeat', AT_4AM)
        service.run_cycle(self.cfg, self.state, AT_4AM + timedelta(minutes=1))
        self.patches['make_dump'].assert_not_called()
        self.patches['flush'].assert_not_called()
        self.patches['send'].assert_not_called()
        self.patches['kuma'].assert_not_called()

    def test_failed_dump_is_recorded_not_raised_and_other_jobs_still_run(self):
        self.patches['make_dump'].side_effect = RuntimeError('mysqldump exited with 2: Access denied')
        self.state.set_dt('last_dump_ok', AT_4AM - timedelta(days=1))
        self.state.set_dt('last_binlog_ship', AT_4AM - timedelta(hours=7))
        summary = service.run_cycle(self.cfg, self.state, AT_4AM)
        self.assertTrue(any('dump:' in e for e in summary['errors']))
        self.assertEqual(self.state.get_dt('last_dump_ok'), AT_4AM.replace(microsecond=0) - timedelta(days=1))
        self.assertIsNotNone(self.state.get_dt('last_dump_attempt'))
        self.patches['flush'].assert_called_once()  # binlog job independent from the dump failure
        self.assertIn('Access denied', self.state.data['last_error'])

    def test_failed_dump_is_retried_after_30_minutes_and_succeeds(self):
        self.state.set_dt('last_dump_ok', AT_4AM - timedelta(days=1))
        self.patches['make_dump'].side_effect = RuntimeError('db down')
        service.run_cycle(self.cfg, self.state, AT_4AM)
        self.patches['make_dump'].side_effect = None
        service.run_cycle(self.cfg, self.state, AT_4AM + timedelta(minutes=10))
        self.assertEqual(self.patches['make_dump'].call_count, 1)  # too early
        service.run_cycle(self.cfg, self.state, AT_4AM + timedelta(minutes=31))
        self.assertEqual(self.patches['make_dump'].call_count, 2)
        self.assertEqual(self.state.get_dt('last_dump_ok').minute, 31)

    def test_binlog_failure_keeps_last_ship_so_health_can_flag_it(self):
        self.patches['flush'].side_effect = CommandError('db down')
        shipped = AT_4AM - timedelta(hours=7)
        self.state.set_dt('last_dump_ok', AT_4AM)
        self.state.set_dt('last_binlog_ship', shipped)
        summary = service.run_cycle(self.cfg, self.state, AT_4AM)
        self.assertTrue(any('binlogs:' in e for e in summary['errors']))
        self.assertEqual(self.state.get_dt('last_binlog_ship'), shipped)
        self.assertEqual(self.state.get_dt('last_binlog_attempt'), AT_4AM.replace(microsecond=0))

    def test_send_failure_is_reported_and_retried_on_the_retry_interval(self):
        self.write_dump('20261107T040000')
        self.state.set_dt('last_dump_ok', AT_4AM)
        self.state.set_dt('last_binlog_ship', AT_4AM)
        self.patches['send'].return_value = SendResult(failed='dump-x.age', error='Connection refused')
        summary = service.run_cycle(self.cfg, self.state, AT_4AM + timedelta(minutes=1))
        self.assertTrue(any('Connection refused' in e for e in summary['errors']))
        service.run_cycle(self.cfg, self.state, AT_4AM + timedelta(minutes=5))
        self.assertEqual(self.patches['send'].call_count, 1)   # not yet
        service.run_cycle(self.cfg, self.state, AT_4AM + timedelta(minutes=17))
        self.assertEqual(self.patches['send'].call_count, 2)   # retried

    def test_heartbeat_reports_down_with_the_reason(self):
        service.run_cycle(self.cfg, self.state, AT_4AM)  # first run: dump mocked ok, but binlogs list empty etc.
        self.patches['kuma'].reset_mock()
        self.state.set_dt('last_dump_ok', AT_4AM - timedelta(hours=40))
        self.state.set_dt('last_dump_attempt', AT_4AM)  # a retry is not due, only the heartbeat is
        self.state.set_dt('last_heartbeat', None)
        self.state.set_dt('last_binlog_ship', AT_4AM)
        service.run_cycle(self.cfg, self.state, AT_4AM + timedelta(minutes=1))
        args = self.patches['kuma'].call_args.args
        self.assertFalse(args[1])
        self.assertIn('old', args[2])

    def test_state_survives_a_restart(self):
        service.run_cycle(self.cfg, self.state, AT_4AM)
        from dbbackup.state import State
        reloaded = State(self.cfg.state_dir / 'state.json')
        self.assertEqual(reloaded.get_dt('last_dump_ok'), AT_4AM.replace(microsecond=0))
        # a "restarted" service must not dump again the same morning
        self.patches['make_dump'].reset_mock()
        service.run_cycle(self.cfg, reloaded, AT_4AM + timedelta(minutes=2))
        self.patches['make_dump'].assert_not_called()

    def test_status_file_is_written_for_the_healthcheck(self):
        service.run_cycle(self.cfg, self.state, AT_4AM)
        self.assertTrue((self.cfg.state_dir / 'status.json').exists())

    def test_local_only_mode_never_tries_to_send(self):
        cfg = self.cfg.__class__(**{**self.cfg.__dict__, 'remote_host': ''})
        self.state.set_dt('last_dump_ok', AT_4AM - timedelta(days=1))
        service.run_cycle(cfg, self.state, AT_4AM)
        self.patches['send'].assert_not_called()


class TestEndToEndWithRealFiles(TmpDirTestCase):
    """Real dump + transfer code with only the external binaries faked."""

    def test_dump_is_encrypted_and_delivered_then_pruned_locally(self):
        import sys
        from dbbackup import dump as dump_mod
        from tests_dbbackup.test_transfer import FakeRun

        fake = FakeRun()
        cmd = [sys.executable, '-c', f'import sys; sys.stdout.write({FAKE_DUMP!r})']
        real_make = dump_mod.make_dump
        with mock.patch.object(transfer, 'run', fake), \
                mock.patch('dbbackup.service.dump.make_dump', lambda cfg, now: real_make(cfg, now, cmd=cmd, env={})), \
                mock.patch('dbbackup.service.binlogs.flush_binary_logs'), \
                mock.patch('dbbackup.service.binlogs.archive_new_binlogs', return_value=[]), \
                mock.patch('dbbackup.service.heartbeat.push_kuma'):
            service.run_cycle(self.cfg, self.state, AT_4AM)

        self.assertEqual(transfer.pending(self.cfg, self.state), [])
        self.assertEqual(fake.rsync_targets(), ['dump-20261107T040005.sql.gz.age', 'dump-20261107T040005.meta.json'])
        self.assertTrue((self.cfg.dumps_dir / 'dump-20261107T040005.sql.gz').exists())


if __name__ == '__main__':
    unittest.main()
