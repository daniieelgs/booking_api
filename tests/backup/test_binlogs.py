import unittest
from unittest import mock

from dbbackup import binlogs
from dbbackup.util import CommandError
from tests.backup.helpers import TmpDirTestCase


class TestParsing(unittest.TestCase):
    def test_binlog_seq(self):
        self.assertEqual(binlogs.binlog_seq('mysql-bin.000012'), 12)
        with self.assertRaises(ValueError):
            binlogs.binlog_seq('mysql-bin.index')

    def test_parse_show_binary_logs(self):
        out = 'mysql-bin.000001\t1024\nmysql-bin.000002\t512\n\n'
        self.assertEqual(binlogs.parse_show_binary_logs(out), ['mysql-bin.000001', 'mysql-bin.000002'])

    def test_parse_empty(self):
        self.assertEqual(binlogs.parse_show_binary_logs(''), [])


class TestArchive(TmpDirTestCase):
    def _patch(self, logs, fetch_side_effect=None):
        p1 = mock.patch.object(binlogs, 'list_server_binlogs', return_value=logs)
        p2 = mock.patch.object(binlogs, 'fetch_and_compress', side_effect=fetch_side_effect)
        m1, m2 = p1.start(), p2.start()
        self.addCleanup(p1.stop)
        self.addCleanup(p2.stop)
        return m1, m2

    def test_skips_the_active_binlog(self):
        _, fetch = self._patch(['b.000001', 'b.000002', 'b.000003'])
        done = binlogs.archive_new_binlogs(self.cfg, self.state)
        self.assertEqual(done, ['b.000001', 'b.000002'])
        self.assertEqual([c.args[1] for c in fetch.call_args_list], ['b.000001', 'b.000002'])

    def test_does_not_refetch_archived_logs(self):
        self.state.mark_archived('b.000001')
        _, fetch = self._patch(['b.000001', 'b.000002', 'b.000003'])
        self.assertEqual(binlogs.archive_new_binlogs(self.cfg, self.state), ['b.000002'])
        fetch.assert_called_once()

    def test_only_active_log_means_nothing_to_do(self):
        _, fetch = self._patch(['b.000001'])
        self.assertEqual(binlogs.archive_new_binlogs(self.cfg, self.state), [])
        fetch.assert_not_called()

    def test_failed_fetch_is_skipped_and_not_marked(self):
        def side(cfg, name):
            if name == 'b.000001':
                raise CommandError('purged')
        self._patch(['b.000001', 'b.000002', 'b.000003'], side)
        self.assertEqual(binlogs.archive_new_binlogs(self.cfg, self.state), ['b.000002'])
        self.assertNotIn('b.000001', self.state.archived_binlogs)

    def test_commands_use_environment_password(self):
        with mock.patch.object(binlogs, 'run') as run:
            run.return_value.stdout = b'b.000001\t1\n'
            binlogs.list_server_binlogs(self.cfg)
            binlogs.flush_binary_logs(self.cfg)
        for call in run.call_args_list:
            self.assertNotIn('s3cret-pw', ' '.join(call.args[0]))
            self.assertEqual(call.kwargs['env'], {'MYSQL_PWD': 's3cret-pw'})
        self.assertIn('FLUSH BINARY LOGS', run.call_args_list[1].args[0])

    def test_fetch_compresses_and_removes_raw(self):
        raw_content = b'\xfebin' + b'x' * 100

        def fake_run(cmd, env=None, timeout=None, **kw):
            result_file = [c for c in cmd if c.startswith('--result-file=')][0].split('=', 1)[1]
            with open(result_file + cmd[-1], 'wb') as f:
                f.write(raw_content)
        with mock.patch.object(binlogs, 'run', side_effect=fake_run):
            path = binlogs.fetch_and_compress(self.cfg, 'b.000007')
        import gzip
        self.assertEqual(path.name, 'b.000007.gz')
        self.assertEqual(gzip.open(path, 'rb').read(), raw_content)
        self.assertEqual([p.name for p in self.cfg.binlogs_dir.iterdir()], ['b.000007.gz'])

    def test_fetch_errors_when_mysqlbinlog_produces_nothing(self):
        with mock.patch.object(binlogs, 'run'):
            with self.assertRaises(CommandError):
                binlogs.fetch_and_compress(self.cfg, 'b.000007')


if __name__ == '__main__':
    unittest.main()
