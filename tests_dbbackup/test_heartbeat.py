import json
import unittest
from datetime import datetime, timedelta
from unittest import mock

from dbbackup import healthcheck, heartbeat
from tests_dbbackup.helpers import TmpDirTestCase

NOW = datetime(2026, 11, 7, 12, 0, 0)


class TestEvaluateHealth(TmpDirTestCase):
    def healthy_state(self):
        self.state.set_dt('last_dump_ok', NOW - timedelta(hours=8))
        self.state.set_dt('last_binlog_ship', NOW - timedelta(hours=2))

    def test_healthy(self):
        self.healthy_state()
        self.assertEqual(heartbeat.evaluate_health(self.cfg, self.state, NOW, None), (True, 'OK'))

    def test_no_dump_yet(self):
        ok, msg = heartbeat.evaluate_health(self.cfg, self.state, NOW, None)
        self.assertFalse(ok)
        self.assertIn('no successful dump', msg)

    def test_stale_dump(self):
        self.healthy_state()
        self.state.set_dt('last_dump_ok', NOW - timedelta(hours=27))
        ok, msg = heartbeat.evaluate_health(self.cfg, self.state, NOW, None)
        self.assertFalse(ok)
        self.assertIn('27h old', msg)

    def test_dump_just_inside_the_limit_is_fine(self):
        self.healthy_state()
        self.state.set_dt('last_dump_ok', NOW - timedelta(hours=26))
        self.assertTrue(heartbeat.evaluate_health(self.cfg, self.state, NOW, None)[0])

    def test_binlogs_not_shipped_for_too_long(self):
        self.healthy_state()
        self.state.set_dt('last_binlog_ship', NOW - timedelta(hours=19))
        ok, msg = heartbeat.evaluate_health(self.cfg, self.state, NOW, None)
        self.assertFalse(ok)
        self.assertIn('binlogs not archived', msg)

    def test_secondary_unreachable_for_more_than_a_day(self):
        self.healthy_state()
        ok, msg = heartbeat.evaluate_health(self.cfg, self.state, NOW, 30.0)
        self.assertFalse(ok)
        self.assertIn('secondary unreachable', msg)

    def test_short_secondary_outage_is_not_an_alert(self):
        self.healthy_state()
        self.assertTrue(heartbeat.evaluate_health(self.cfg, self.state, NOW, 3.0)[0])

    def test_pending_is_ignored_when_there_is_no_secondary(self):
        cfg = self.cfg.__class__(**{**self.cfg.__dict__, 'remote_host': ''})
        self.healthy_state()
        self.assertTrue(heartbeat.evaluate_health(cfg, self.state, NOW, 100.0)[0])

    def test_all_problems_are_listed_together(self):
        ok, msg = heartbeat.evaluate_health(self.cfg, self.state, NOW, 50.0)
        self.assertFalse(ok)
        self.assertEqual(msg.count(';'), 2)


class TestPushKuma(unittest.TestCase):
    def _resp(self, status=200):
        resp = mock.MagicMock()
        resp.status = status
        resp.__enter__.return_value = resp
        return resp

    def test_up_request(self):
        with mock.patch('urllib.request.urlopen', return_value=self._resp()) as op:
            self.assertTrue(heartbeat.push_kuma('https://kuma.example/api/push/abc', True, 'OK'))
        url = op.call_args.args[0]
        self.assertTrue(url.startswith('https://kuma.example/api/push/abc?'))
        self.assertIn('status=up', url)

    def test_down_request_keeps_existing_query_string(self):
        with mock.patch('urllib.request.urlopen', return_value=self._resp()) as op:
            heartbeat.push_kuma('https://kuma.example/api/push/abc?ping=', False, 'bad: stale dump')
        url = op.call_args.args[0]
        self.assertIn('?ping=&status=down', url)
        self.assertIn('msg=bad%3A+stale+dump', url)

    def test_network_errors_never_propagate(self):
        with mock.patch('urllib.request.urlopen', side_effect=OSError('unreachable')):
            self.assertFalse(heartbeat.push_kuma('https://kuma.example/x', True, 'OK'))

    def test_no_url_is_a_noop(self):
        with mock.patch('urllib.request.urlopen') as op:
            self.assertFalse(heartbeat.push_kuma('', True, 'OK'))
        op.assert_not_called()

    def test_long_messages_are_truncated(self):
        with mock.patch('urllib.request.urlopen', return_value=self._resp()) as op:
            heartbeat.push_kuma('https://k/x', False, 'e' * 1000)
        self.assertLess(len(op.call_args.args[0]), 400)


class TestStatusAndHealthcheck(TmpDirTestCase):
    def test_status_file_roundtrip_and_alive(self):
        heartbeat.write_status(self.cfg, self.state, NOW, True, 'OK', 0)
        data = json.loads((self.cfg.state_dir / 'status.json').read_text())
        self.assertEqual((data['healthy'], data['message'], data['pending']), (True, 'OK', 0))
        self.assertTrue(healthcheck.is_alive(str(self.dir), now=NOW + timedelta(minutes=5)))

    def test_stale_status_means_dead_loop(self):
        heartbeat.write_status(self.cfg, self.state, NOW, True, 'OK', 0)
        self.assertFalse(healthcheck.is_alive(str(self.dir), now=NOW + timedelta(minutes=16)))

    def test_missing_or_corrupt_status(self):
        self.assertFalse(healthcheck.is_alive(str(self.dir), now=NOW))
        (self.cfg.state_dir / 'status.json').write_text('garbage')
        self.assertFalse(healthcheck.is_alive(str(self.dir), now=NOW))

    def test_unhealthy_backups_do_not_fail_the_container_healthcheck(self):
        heartbeat.write_status(self.cfg, self.state, NOW, False, 'last dump is 30h old', 3)
        self.assertTrue(healthcheck.is_alive(str(self.dir), now=NOW))


if __name__ == '__main__':
    unittest.main()
