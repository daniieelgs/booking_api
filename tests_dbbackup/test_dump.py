import gzip
import json
import sys
import unittest
from datetime import datetime

from dbbackup import dump
from dbbackup.dump import DumpError, dump_command, make_dump, parse_binlog_position
from tests_dbbackup.helpers import FAKE_DUMP, TmpDirTestCase


def fake_cmd(text: str, exit_code: int = 0):
    return [sys.executable, '-c',
            f'import sys; sys.stdout.write({text!r}); sys.stderr.write("boom"); sys.exit({exit_code})']


class TestParse(unittest.TestCase):
    def test_parses_commented_master_data_line(self):
        self.assertEqual(parse_binlog_position(FAKE_DUMP), ('mysql-bin.000003', 328))

    def test_parses_uncommented_form(self):
        self.assertEqual(parse_binlog_position("CHANGE MASTER TO MASTER_LOG_FILE='b.000010', MASTER_LOG_POS=4;"),
                         ('b.000010', 4))

    def test_none_when_absent(self):
        self.assertIsNone(parse_binlog_position('-- nothing here'))

    def test_dump_stamp(self):
        self.assertEqual(dump.dump_stamp('dump-20261107T040000.sql.gz'), '20261107T040000')
        self.assertIsNone(dump.dump_stamp('dump-20261107T040000.sql.gz.age'))


class TestDumpCommand(TmpDirTestCase):
    def test_hot_consistent_and_never_contains_password(self):
        cmd = dump_command(self.cfg)
        for flag in ('--single-transaction', '--master-data=2', '--flush-logs', '--routines', '--events', '--triggers'):
            self.assertIn(flag, cmd)
        self.assertEqual(cmd[0], 'mariadb-dump')  # the legacy mysql* aliases do not exist in 11.x clients
        self.assertEqual(cmd[-2:], ['--databases', 'bbdd'])
        self.assertNotIn('s3cret-pw', ' '.join(cmd))
        self.assertNotIn('-p', [c for c in cmd if c.startswith('-p')])


class TestMakeDump(TmpDirTestCase):
    NOW = datetime(2026, 11, 7, 4, 0, 0)

    def test_success_writes_gz_and_meta(self):
        meta = make_dump(self.cfg, self.NOW, cmd=fake_cmd(FAKE_DUMP), env={})
        data = self.cfg.dumps_dir / 'dump-20261107T040000.sql.gz'
        self.assertTrue(data.exists())
        self.assertEqual(gzip.open(data, 'rt').read(), FAKE_DUMP)
        self.assertEqual(meta['binlog_file'], 'mysql-bin.000003')
        self.assertEqual(meta['binlog_pos'], 328)
        self.assertEqual(meta['created'], '2026-11-07T04:00:00')
        on_disk = json.loads((self.cfg.dumps_dir / 'dump-20261107T040000.meta.json').read_text())
        self.assertEqual(on_disk, meta)
        self.assertEqual(len(meta['sha256']), 64)
        self.assertEqual([p.name for p in self.cfg.dumps_dir.glob('*.partial')], [])

    def test_failed_command_leaves_nothing_behind(self):
        with self.assertRaises(DumpError) as ctx:
            make_dump(self.cfg, self.NOW, cmd=fake_cmd(FAKE_DUMP, exit_code=2), env={})
        self.assertIn('boom', str(ctx.exception))
        self.assertEqual(list(self.cfg.dumps_dir.iterdir()), [])

    def test_truncated_dump_is_rejected(self):
        truncated = FAKE_DUMP.replace('-- Dump completed on 2026-11-07 4:00:03\n', '')
        with self.assertRaises(DumpError) as ctx:
            make_dump(self.cfg, self.NOW, cmd=fake_cmd(truncated), env={})
        self.assertIn('truncated', str(ctx.exception))
        self.assertEqual(list(self.cfg.dumps_dir.iterdir()), [])

    def test_dump_without_binlog_position_is_rejected(self):
        no_pos = FAKE_DUMP.replace("-- CHANGE MASTER TO MASTER_LOG_FILE='mysql-bin.000003', MASTER_LOG_POS=328;\n", '')
        with self.assertRaises(DumpError) as ctx:
            make_dump(self.cfg, self.NOW, cmd=fake_cmd(no_pos), env={})
        self.assertIn('log_bin', str(ctx.exception))
        self.assertEqual(list(self.cfg.dumps_dir.iterdir()), [])

    def test_sandbox_mode_header_of_new_clients_is_removed(self):
        # mariadb-dump 10.11.x/11.x emits this first line; the 10.5 server's client cannot parse it.
        with_header = '/*M!999999\\- enable the sandbox mode */\n' + FAKE_DUMP
        make_dump(self.cfg, self.NOW, cmd=fake_cmd(with_header), env={})
        text = gzip.open(self.cfg.dumps_dir / 'dump-20261107T040000.sql.gz', 'rt').read()
        self.assertNotIn('sandbox', text)
        self.assertEqual(text, FAKE_DUMP)

    def test_missing_binary_is_a_clear_error(self):
        from dbbackup.util import CommandError
        with self.assertRaises(CommandError):
            make_dump(self.cfg, self.NOW, cmd=['definitely-not-a-binary-xyz'], env={})

    def test_password_goes_through_environment_only(self):
        script = ('import os,sys; sys.stdout.write(%r) if os.environ.get("MYSQL_PWD")=="s3cret-pw" else sys.exit(9)'
                  % FAKE_DUMP)
        make_dump(self.cfg, self.NOW, cmd=[sys.executable, '-c', script])  # default env carries MYSQL_PWD

    def test_list_dumps_only_returns_complete_ones_oldest_first(self):
        self.write_dump('20261105T040000')
        self.write_dump('20261107T040000')
        orphan = self.write_dump('20261106T040000')
        (self.cfg.dumps_dir / orphan).unlink()  # meta without data
        found = [m['name'] for m, _ in dump.list_dumps(self.cfg.dumps_dir)]
        self.assertEqual(found, ['dump-20261105T040000.sql.gz', 'dump-20261107T040000.sql.gz'])


if __name__ == '__main__':
    unittest.main()
