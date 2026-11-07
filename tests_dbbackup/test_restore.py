import gzip
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

from dbbackup import restore
from dbbackup.restore import Conn, RestoreError
from tests_dbbackup.helpers import TmpDirTestCase


class TestUntil(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(restore.parse_until('2026-11-07 10:31:50'), datetime(2026, 11, 7, 10, 31, 50))

    def test_rejects_other_formats(self):
        for bad in ('2026-11-07', '07/11/2026 10:31', 'yesterday', ''):
            with self.subTest(bad=bad):
                with self.assertRaises(RestoreError):
                    restore.parse_until(bad)


class TestBaseDumpSelection(TmpDirTestCase):
    def setUp(self):
        super().setUp()
        self.write_dump('20261105T040000', 'mysql-bin.000010', 4)
        self.write_dump('20261106T040000', 'mysql-bin.000020', 100)
        self.write_dump('20261107T040000', 'mysql-bin.000030', 200)

    def test_picks_newest_dump_not_after_until(self):
        meta, data = restore.find_base_dump(self.cfg.dumps_dir, datetime(2026, 11, 7, 10, 31, 50))
        self.assertEqual(meta['name'], 'dump-20261107T040000.sql.gz')
        self.assertEqual(data.name, meta['name'])

    def test_until_before_todays_dump_uses_yesterdays(self):
        meta, _ = restore.find_base_dump(self.cfg.dumps_dir, datetime(2026, 11, 7, 3, 59, 59))
        self.assertEqual(meta['name'], 'dump-20261106T040000.sql.gz')

    def test_until_exactly_at_dump_time_is_included(self):
        meta, _ = restore.find_base_dump(self.cfg.dumps_dir, datetime(2026, 11, 7, 4, 0, 0))
        self.assertEqual(meta['name'], 'dump-20261107T040000.sql.gz')

    def test_no_dump_old_enough(self):
        with self.assertRaises(RestoreError) as ctx:
            restore.find_base_dump(self.cfg.dumps_dir, datetime(2026, 11, 1, 0, 0, 0))
        self.assertIn('No local dump', str(ctx.exception))

    def test_empty_dir(self):
        with self.assertRaises(RestoreError):
            restore.find_base_dump(self.dir / 'nothing', datetime(2026, 11, 7))


class TestBinlogSelection(TmpDirTestCase):
    def test_from_start_file_onward(self):
        logs = ['b.000001', 'b.000002', 'b.000003', 'b.000004']
        self.assertEqual(restore.binlogs_from(logs, 'b.000002'), ['b.000002', 'b.000003', 'b.000004'])

    def test_purged_start_file_is_a_clear_error(self):
        with self.assertRaises(RestoreError) as ctx:
            restore.binlogs_from(['b.000005', 'b.000006'], 'b.000002')
        self.assertIn('--source archive', str(ctx.exception))

    def test_archive_listing(self):
        for n in ('b.000001', 'b.000002', 'b.000003'):
            self.write_binlog(n)
        (self.cfg.binlogs_dir / 'junk.gz').write_bytes(b'x')
        self.assertEqual(restore.archived_binlogs_from(self.cfg.binlogs_dir, 'b.000002'), ['b.000002', 'b.000003'])

    def test_mysqlbinlog_command_live(self):
        cmd = restore.mysqlbinlog_command(self.cfg, ['b.000002', 'b.000003'], 328, datetime(2026, 11, 7, 10, 31, 50),
                                          remote=True, database='bbdd')
        self.assertEqual(cmd[0], 'mariadb-binlog')
        self.assertIn('--read-from-remote-server', cmd)
        self.assertIn('--start-position=328', cmd)
        self.assertIn('--stop-datetime=2026-11-07 10:31:50', cmd)
        self.assertIn('--database=bbdd', cmd)
        self.assertEqual(cmd[-2:], ['b.000002', 'b.000003'])
        self.assertNotIn('s3cret-pw', ' '.join(cmd))

    def test_mysqlbinlog_command_local_has_no_connection_flags(self):
        cmd = restore.mysqlbinlog_command(self.cfg, ['/tmp/x'], 4, None, remote=False, database=None)
        self.assertNotIn('--read-from-remote-server', cmd)
        self.assertFalse(any(c.startswith('--stop-datetime') for c in cmd))
        self.assertNotIn('-h', cmd)


class TestWhereBuilding(unittest.TestCase):
    def test_single_column_key(self):
        self.assertEqual(restore.build_where(['id'], [('1',), ('5',)]), "`id` IN ('1','5')")

    def test_char_hex_key(self):
        self.assertEqual(restore.build_where(['id'], [('151b1bf60f3e4026814183ffe9c75148',)]),
                         "`id` IN ('151b1bf60f3e4026814183ffe9c75148')")

    def test_composite_key(self):
        self.assertEqual(restore.build_where(['a', 'b'], [('1', 'x'), ('2', 'y')]),
                         "(`a`,`b`) IN (('1','x'),('2','y'))")

    def test_values_that_could_inject_sql_are_refused(self):
        for evil in ("1'); DROP TABLE booking;--", "a'b", 'x"y', 'a;b', 'a\\b'):
            with self.subTest(evil=evil):
                with self.assertRaises(RestoreError):
                    restore.build_where(['id'], [(evil,)])

    def test_unsafe_identifiers_are_refused(self):
        with self.assertRaises(RestoreError):
            restore.build_where(['id`; DROP'], [('1',)])

    def test_missing_keys(self):
        past = {('1',), ('2',), ('3',)}
        live = {('2',), ('4',)}
        self.assertEqual(restore.missing_keys(past, live), [('1',), ('3',)])

    def test_nothing_missing(self):
        self.assertEqual(restore.missing_keys({('1',)}, {('1',), ('2',)}), [])

    def test_chunking(self):
        self.assertEqual([len(c) for c in restore.chunked(list(range(1201)), 500)], [500, 500, 201])
        self.assertEqual(list(restore.chunked([], 500)), [])


class FakeMysql:
    """Fake scratch and live servers answering the few queries restore.py issues."""

    def __init__(self, tables, pks, keys):
        self.tables, self.pks, self.keys = tables, pks, keys  # keys: {(host, table): [rows]}

    def conn_query(self, conn, sql):
        if 'information_schema.TABLES' in sql:
            return [[t] for t in self.tables]
        if 'KEY_COLUMN_USAGE' in sql:
            table = sql.split("TABLE_NAME='")[1].split("'")[0]
            return [[c] for c in self.pks.get(table, [])]
        if sql.startswith('SELECT') and 'FROM `bbdd`' in sql:
            table = sql.split('`.`')[1].split('`')[0]
            return [list(r) for r in self.keys[(conn.host, table)]]
        raise AssertionError(sql)


class TestGenerateRecoverySql(TmpDirTestCase):
    def setUp(self):
        super().setUp()
        self.scratch = Conn('restore-db', 3306, 'root', 'scratch-pw')
        self.live = Conn('database', 3306, 'backup', 'live-pw')
        self.fake = FakeMysql(
            tables=['booking', 'service_booking', 'status', 'nopk'],
            pks={'booking': ['id'], 'service_booking': ['id'], 'status': ['id']},
            keys={('restore-db', 'booking'): [('1',), ('2',), ('3',), ('4',)],
                  ('database', 'booking'): [('1',), ('4',)],
                  ('restore-db', 'service_booking'): [('10',), ('11',)],
                  ('database', 'service_booking'): [('10',), ('11',)],
                  ('restore-db', 'status'): [('1',)], ('database', 'status'): [('1',)]})
        self.dumped = []

        def fake_run(cmd, env=None, timeout=None, **kw):
            self.dumped.append((cmd, env))
            where = [c for c in cmd if c.startswith('--where=')][0]
            return mock.Mock(stdout=f'INSERT IGNORE INTO `{cmd[-1]}` VALUES (...); -- {where}\n'.encode())

        for target, side in (('dbbackup.restore.Conn.query', lambda conn, sql: self.fake.conn_query(conn, sql)),):
            p = mock.patch(target, autospec=True, side_effect=side)
            p.start(); self.addCleanup(p.stop)
        p = mock.patch.object(restore, 'run', side_effect=fake_run)
        p.start(); self.addCleanup(p.stop)
        self.out = self.dir / 'restore' / 'recovered.sql'

    def test_generates_inserts_only_for_rows_missing_today(self):
        summary = restore.generate_recovery_sql(self.scratch, self.live, 'bbdd', self.out)
        self.assertEqual(dict(summary), {'booking': 2, 'service_booking': 0, 'status': 0})
        sql = self.out.read_text()
        self.assertIn("`id` IN ('2','3')", sql)
        self.assertEqual(sql.count('INSERT IGNORE'), 1)
        self.assertTrue(sql.startswith('-- Rows recovered'))
        self.assertIn('SET FOREIGN_KEY_CHECKS=0;', sql)
        self.assertTrue(sql.rstrip().endswith('SET UNIQUE_CHECKS=1;'))

    def test_sandbox_header_is_stripped_from_generated_sql(self):
        # restore.sh --apply pipes this file into the 10.5 server's mysql client
        def with_header(cmd, env=None, timeout=None, **kw):
            return mock.Mock(stdout=b'/*M!999999\\- enable the sandbox mode */\nINSERT IGNORE INTO t VALUES (1);\n')
        with mock.patch.object(restore, 'run', side_effect=with_header):
            restore.generate_recovery_sql(self.scratch, self.live, 'bbdd', self.out, only_tables=['booking'])
        self.assertNotIn('sandbox', self.out.read_text())
        self.assertIn('INSERT IGNORE INTO t', self.out.read_text())

    def test_table_without_primary_key_is_skipped_not_fatal(self):
        summary = restore.generate_recovery_sql(self.scratch, self.live, 'bbdd', self.out)
        self.assertNotIn('nopk', summary)

    def test_restricting_to_some_tables(self):
        summary = restore.generate_recovery_sql(self.scratch, self.live, 'bbdd', self.out, only_tables=['status'])
        self.assertEqual(list(summary), ['status'])

    def test_unknown_table_is_an_error(self):
        with self.assertRaises(RestoreError):
            restore.generate_recovery_sql(self.scratch, self.live, 'bbdd', self.out, only_tables=['bookin'])

    def test_rows_are_dumped_from_scratch_never_from_live_and_password_not_in_argv(self):
        restore.generate_recovery_sql(self.scratch, self.live, 'bbdd', self.out)
        cmd, env = self.dumped[0]
        self.assertIn('restore-db', cmd)
        self.assertNotIn('database', cmd[:cmd.index('--no-create-info')])
        self.assertEqual(env, {'MYSQL_PWD': 'scratch-pw'})
        self.assertNotIn('scratch-pw', ' '.join(cmd))
        for flag in ('--no-create-info', '--insert-ignore', '--skip-triggers', '--complete-insert'):
            self.assertIn(flag, cmd)

    def test_nothing_lost_produces_an_empty_but_valid_script(self):
        self.fake.keys[('database', 'booking')] = [('1',), ('2',), ('3',), ('4',)]
        summary = restore.generate_recovery_sql(self.scratch, self.live, 'bbdd', self.out)
        self.assertEqual(sum(summary.values()), 0)
        self.assertEqual(self.dumped, [])
        self.assertNotIn('INSERT', self.out.read_text())

    def test_large_loss_is_split_in_chunks(self):
        self.fake.keys[('restore-db', 'booking')] = [(str(i),) for i in range(1, 1202)]
        self.fake.keys[('database', 'booking')] = []
        restore.generate_recovery_sql(self.scratch, self.live, 'bbdd', self.out, only_tables=['booking'])
        self.assertEqual(len(self.dumped), 3)


class TestLoadAndReplay(TmpDirTestCase):
    def test_archive_replay_refuses_gaps(self):
        scratch = Conn('restore-db', 3306, 'root', 'x')
        with self.assertRaises(RestoreError):
            restore.replay_binlogs(self.cfg, scratch, ['b.000001'], 4, datetime(2026, 11, 7), 'archive')

    def test_archive_replay_decompresses_and_pipes_to_scratch(self):
        p = self.cfg.binlogs_dir
        p.mkdir(parents=True, exist_ok=True)
        with gzip.open(p / 'b.000001.gz', 'wb') as f:
            f.write(b'RAWBINLOG')
        seen = {}

        def fake_pipeline(first, first_env, second, second_env):
            seen.update(first=first, first_env=first_env, second=second, second_env=second_env,
                        content=Path(first[-1]).read_bytes())
        with mock.patch.object(restore, 'run_pipeline', side_effect=fake_pipeline):
            restore.replay_binlogs(self.cfg, Conn('restore-db', 3306, 'root', 'pw'), ['b.000001'], 4,
                                   datetime(2026, 11, 7, 10, 0, 0), 'archive')
        self.assertEqual(seen['content'], b'RAWBINLOG')
        self.assertNotIn('--read-from-remote-server', seen['first'])
        self.assertEqual(seen['second'][0], 'mariadb')
        self.assertIn('restore-db', seen['second'])

    def test_live_replay_uses_the_backup_user_for_reading(self):
        seen = {}
        with mock.patch.object(restore, 'run_pipeline', side_effect=lambda *a: seen.setdefault('a', a)):
            restore.replay_binlogs(self.cfg, Conn('restore-db', 3306, 'root', 'pw'), ['b.000001'], 4,
                                   datetime(2026, 11, 7, 10, 0, 0), 'live')
        first, first_env, second, second_env = seen['a']
        self.assertIn('--read-from-remote-server', first)
        self.assertEqual(first_env, {'MYSQL_PWD': 's3cret-pw'})
        self.assertEqual(second_env, {'MYSQL_PWD': 'pw'})

    def test_no_files_is_a_noop(self):
        with mock.patch.object(restore, 'run_pipeline') as rp:
            restore.replay_binlogs(self.cfg, Conn('h', 1, 'u', 'p'), [], 4, datetime(2026, 11, 7), 'live')
        rp.assert_not_called()


class TestRunRestore(TmpDirTestCase):
    def setUp(self):
        super().setUp()
        self.write_dump('20261107T040000', 'b.000030', 200)

    def _run(self, source, **patches):
        scratch = Conn('restore-db', 3306, 'root', 'pw')
        with mock.patch.object(restore, 'wait_for_db'), \
                mock.patch.object(restore.Conn, 'query'), \
                mock.patch.object(restore, 'load_dump') as load, \
                mock.patch.object(restore, 'replay_binlogs') as replay, \
                mock.patch.object(restore, 'generate_recovery_sql', return_value={'booking': 2}) as gen, \
                mock.patch.object(restore, 'list_server_binlogs', return_value=['b.000029', 'b.000030', 'b.000031']):
            result = restore.run_restore(self.cfg, datetime(2026, 11, 7, 10, 31, 50), scratch,
                                         self.dir / 'out.sql', source, None)
        return result, load, replay, gen

    def test_live_flow_loads_dump_then_replays_from_its_position(self):
        result, load, replay, gen = self._run('live')
        self.assertEqual(result, {'booking': 2})
        self.assertEqual(load.call_args.args[1].name, 'dump-20261107T040000.sql.gz')
        args = replay.call_args.args
        self.assertEqual(args[2], ['b.000030', 'b.000031'])  # from the dump's file onward
        self.assertEqual(args[3], 200)                       # at the dump's position
        self.assertEqual(args[4], datetime(2026, 11, 7, 10, 31, 50))

    def test_archive_flow_requires_the_start_binlog(self):
        self.write_binlog('b.000031')  # start file b.000030 missing from the archive
        with self.assertRaises(RestoreError):
            self._run('archive')

    def test_archive_flow_ok(self):
        self.write_binlog('b.000030'); self.write_binlog('b.000031')
        _, _, replay, _ = self._run('archive')
        self.assertEqual(replay.call_args.args[2], ['b.000030', 'b.000031'])


class TestInspect(unittest.TestCase):
    SAMPLE = """\
#261107 10:31:12 server id 1  end_log_pos 600 CRC32 0x1  Write_rows: table id 25 flags: STMT_END_F
### INSERT INTO `bbdd`.`booking`
### SET
###   @1=9
#261107 10:32:05 server id 1  end_log_pos 900 CRC32 0x2  Delete_rows: table id 25 flags: STMT_END_F
### DELETE FROM `bbdd`.`booking`
### WHERE
###   @1=1
### DELETE FROM `bbdd`.`booking`
### WHERE
###   @1=2
### DELETE FROM `bbdd`.`service_booking`
### WHERE
###   @1=7
#261107 9:05:00 server id 1  end_log_pos 1200 CRC32 0x3  Update_rows: table id 25 flags: STMT_END_F
### UPDATE `bbdd`.`worker`
### WHERE
"""

    def test_summarizes_deletes_and_updates_with_timestamps(self):
        got = restore.summarize_row_events(self.SAMPLE.splitlines())
        self.assertEqual(got, [('2026-11-07 10:32:05', 'DELETE', 'bbdd.booking', 2),
                               ('2026-11-07 10:32:05', 'DELETE', 'bbdd.service_booking', 1),
                               ('2026-11-07 09:05:00', 'UPDATE', 'bbdd.worker', 1)])

    def test_inserts_are_hidden_by_default_but_selectable(self):
        got = restore.summarize_row_events(self.SAMPLE.splitlines(), ops=('INSERT',))
        self.assertEqual(got, [('2026-11-07 10:31:12', 'INSERT', 'bbdd.booking', 1)])

    def test_only_deletes(self):
        got = restore.summarize_row_events(self.SAMPLE.splitlines(), ops=('delete',))
        self.assertEqual({op for _, op, _, _ in got}, {'DELETE'})

    def test_empty(self):
        self.assertEqual(restore.summarize_row_events([]), [])


if __name__ == '__main__':
    unittest.main()
