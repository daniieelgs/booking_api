import json
import os
import time
import unittest
from datetime import datetime, timedelta
from pathlib import Path
import tempfile

from dbbackup import prune, transfer
from tests_dbbackup.helpers import TmpDirTestCase

D = ['dump-20261101T040000.sql.gz.age', 'dump-20261102T040000.sql.gz.age', 'dump-20261103T040000.sql.gz.age',
     'dump-20261104T040000.sql.gz.age', 'dump-20261105T040000.sql.gz.age']


class TestPureRules(unittest.TestCase):
    def test_keeps_newest_n(self):
        self.assertEqual(prune.dumps_to_delete(D, 3), D[:2])

    def test_keep_more_than_exist_deletes_nothing(self):
        self.assertEqual(prune.dumps_to_delete(D, 10), [])

    def test_protected_are_never_deleted(self):
        self.assertEqual(prune.dumps_to_delete(D, 2, protected=[D[0]]), D[1:3])

    def test_order_of_input_is_irrelevant(self):
        self.assertEqual(prune.dumps_to_delete(list(reversed(D)), 3), D[:2])

    def test_ignores_non_dump_files(self):
        self.assertEqual(prune.dumps_to_delete(['notes.txt', 'mysql-bin.000001.gz'] + D, 5), [])

    def test_binlogs_older_than_seq(self):
        names = ['mysql-bin.000001.gz.age', 'mysql-bin.000004.gz.age', 'mysql-bin.000005.gz.age', 'x.txt']
        self.assertEqual(prune.binlogs_older_than_seq(names, 5), names[:2])


class TestPruneRemoteDir(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.d = Path(self._tmp.name)

    def _dump(self, stamp, binlog_seq, with_meta=True):
        (self.d / f'dump-{stamp}.sql.gz.age').write_bytes(b'x')
        if with_meta:
            (self.d / f'dump-{stamp}.meta.json').write_text(
                json.dumps({'binlog_file': f'mysql-bin.{binlog_seq:06d}', 'binlog_pos': 4}))

    def _binlog(self, seq):
        (self.d / f'mysql-bin.{seq:06d}.gz.age').write_bytes(b'x')

    def names(self):
        return sorted(p.name for p in self.d.iterdir())

    def test_keeps_three_dumps_and_the_binlogs_they_need(self):
        for i, stamp in enumerate(['20261101', '20261102', '20261103', '20261104', '20261105'], start=1):
            self._dump(stamp + 'T040000', binlog_seq=i * 2)
        for seq in range(1, 12):
            self._binlog(seq)
        deleted = prune.prune_remote_dir(self.d, keep_dumps=3)
        left = self.names()
        self.assertEqual(sum(1 for n in left if n.endswith('.sql.gz.age')), 3)
        self.assertIn('dump-20261103T040000.sql.gz.age', left)
        self.assertNotIn('dump-20261102T040000.sql.gz.age', left)
        self.assertNotIn('dump-20261102T040000.meta.json', left)
        # oldest kept dump is #3 -> binlog_file 000006: binlogs < 6 are not needed any more
        self.assertNotIn('mysql-bin.000005.gz.age', left)
        self.assertIn('mysql-bin.000006.gz.age', left)
        self.assertIn('mysql-bin.000011.gz.age', left)
        self.assertTrue(deleted)

    def test_dry_run_deletes_nothing(self):
        for i, stamp in enumerate(['20261101', '20261102', '20261103', '20261104'], start=1):
            self._dump(stamp + 'T040000', binlog_seq=i)
        before = self.names()
        deleted = prune.prune_remote_dir(self.d, keep_dumps=2, dry_run=True)
        self.assertTrue(deleted)
        self.assertEqual(self.names(), before)

    def test_incomplete_dump_without_meta_is_not_counted_as_a_backup(self):
        self._dump('20261101T040000', 1)
        self._dump('20261102T040000', 2)
        self._dump('20261103T040000', 3, with_meta=False)  # transfer interrupted before the meta
        prune.prune_remote_dir(self.d, keep_dumps=2)
        # the two complete ones are kept even though a newer, incomplete file exists
        self.assertIn('dump-20261101T040000.sql.gz.age', self.names())
        self.assertIn('dump-20261102T040000.sql.gz.age', self.names())

    def test_unreadable_meta_never_deletes_binlogs(self):
        self._dump('20261101T040000', 1)
        (self.d / 'dump-20261101T040000.meta.json').write_text('{not json')
        for seq in (1, 2, 3):
            self._binlog(seq)
        prune.prune_remote_dir(self.d, keep_dumps=1)
        self.assertEqual(len([n for n in self.names() if n.startswith('mysql-bin')]), 3)

    def test_stale_rsync_temp_files_are_removed_but_fresh_ones_are_not(self):
        stale = self.d / '.dump-20261101T040000.sql.gz.age.AbC123'
        fresh = self.d / '.dump-20261102T040000.sql.gz.age.XyZ789'
        stale.write_bytes(b'x'); fresh.write_bytes(b'x')
        old = time.time() - 3 * 86400
        os.utime(stale, (old, old))
        prune.prune_remote_dir(self.d, keep_dumps=3)
        self.assertFalse(stale.exists())
        self.assertTrue(fresh.exists())

    def test_empty_directory(self):
        self.assertEqual(prune.prune_remote_dir(self.d, keep_dumps=3), [])

    def test_cli_rejects_bad_arguments(self):
        self.assertEqual(prune.main(['--dir', str(self.d / 'missing'), '--keep-dumps', '3']), 2)
        self.assertEqual(prune.main(['--dir', str(self.d), '--keep-dumps', '0']), 2)
        self.assertEqual(prune.main(['--dir', str(self.d), '--keep-dumps', '3']), 0)


class TestPruneLocal(TmpDirTestCase):
    NOW = datetime(2026, 11, 7, 12, 0, 0)

    def test_keeps_two_newest_dumps_when_everything_was_delivered(self):
        for stamp in ('20261104', '20261105', '20261106', '20261107'):
            name = self.write_dump(stamp + 'T040000')
            self.state.mark_sent(name + '.age', self.NOW)
        deleted = transfer.prune_local(self.cfg, self.state, self.NOW)
        self.assertEqual(sorted(deleted), ['dump-20261104T040000.sql.gz', 'dump-20261105T040000.sql.gz'])
        left = sorted(p.name for p in self.cfg.dumps_dir.iterdir())
        self.assertEqual(left, ['dump-20261106T040000.meta.json', 'dump-20261106T040000.sql.gz',
                                'dump-20261107T040000.meta.json', 'dump-20261107T040000.sql.gz'])

    def test_undelivered_dumps_are_protected_while_the_secondary_is_down(self):
        for stamp in ('20261104', '20261105', '20261106', '20261107'):
            self.write_dump(stamp + 'T040000')  # none delivered
        self.assertEqual(transfer.prune_local(self.cfg, self.state, self.NOW), [])
        self.assertEqual(len(list(self.cfg.dumps_dir.glob('*.sql.gz'))), 4)

    def test_unsent_protection_is_capped_so_the_disk_cannot_fill_up(self):
        cfg = self.cfg.__class__(**{**self.cfg.__dict__, 'max_unsent_dumps': 3, 'local_keep_dumps': 1})
        for day in range(1, 8):
            self.write_dump(f'202611{day:02d}T040000')
        deleted = transfer.prune_local(cfg, self.state, self.NOW)
        self.assertEqual(len(deleted), 4)  # 7 dumps - 3 protected (the newest 3, which include the kept one)
        self.assertEqual(len(list(cfg.dumps_dir.glob('*.sql.gz'))), 3)

    def test_without_a_secondary_nothing_is_ever_protected(self):
        cfg = self.cfg.__class__(**{**self.cfg.__dict__, 'remote_host': ''})
        for stamp in ('20261105', '20261106', '20261107'):
            self.write_dump(stamp + 'T040000')
        self.assertEqual(len(transfer.prune_local(cfg, self.state, self.NOW)), 1)

    def test_old_binlogs_removed_only_if_delivered(self):
        old = self.NOW.timestamp() - 9 * 86400
        recent = self.NOW.timestamp() - 2 * 86400
        self.write_binlog('mysql-bin.000001', mtime=old)    # old + delivered   -> delete
        self.write_binlog('mysql-bin.000002', mtime=old)    # old + undelivered -> keep
        self.write_binlog('mysql-bin.000003', mtime=recent)  # recent            -> keep
        self.state.mark_sent('mysql-bin.000001.gz.age', self.NOW)
        self.assertEqual(transfer.prune_local(self.cfg, self.state, self.NOW), ['mysql-bin.000001.gz'])
        left = sorted(p.name for p in self.cfg.binlogs_dir.iterdir())
        self.assertEqual(left, ['mysql-bin.000002.gz', 'mysql-bin.000003.gz'])


if __name__ == '__main__':
    unittest.main()
