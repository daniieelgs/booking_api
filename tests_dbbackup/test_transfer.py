import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

from dbbackup import transfer
from dbbackup.util import CommandError
from tests_dbbackup.helpers import TmpDirTestCase

NOW = datetime(2026, 11, 7, 12, 0, 0)


class FakeRun:
    """Stands in for util.run: `age` writes its output file, `rsync` succeeds or fails on demand."""

    def __init__(self):
        self.calls = []
        self.rsync_fails = False
        self.age_fails = False

    def __call__(self, cmd, env=None, input_bytes=None, timeout=None, check=True):
        self.calls.append(list(cmd))
        if cmd[0] == 'age':
            if self.age_fails:
                raise CommandError('age: boom')
            with open(cmd[cmd.index('-o') + 1], 'wb') as f:
                f.write(b'ENCRYPTED')
        elif cmd[0] == 'rsync':
            if self.rsync_fails:
                raise CommandError('rsync exited with 255: ssh: connect to host secondary: Connection refused')
        return mock.Mock(returncode=0, stdout=b'', stderr=b'')

    def rsync_targets(self):
        return [c[-2].split('\\')[-1].split('/')[-1] for c in self.calls if c[0] == 'rsync']


class TestArtifacts(TmpDirTestCase):
    def test_dump_data_is_followed_by_its_meta_and_binlogs_come_after(self):
        self.write_dump('20261107T040000')
        self.write_binlog('mysql-bin.000004')
        names = [a.remote_name for a in transfer.local_artifacts(self.cfg)]
        self.assertEqual(names, ['dump-20261107T040000.sql.gz.age', 'dump-20261107T040000.meta.json',
                                 'mysql-bin.000004.gz.age'])

    def test_encryption_flags(self):
        self.write_dump('20261107T040000')
        self.write_binlog('mysql-bin.000004')
        flags = {a.remote_name: a.encrypt for a in transfer.local_artifacts(self.cfg)}
        self.assertTrue(flags['dump-20261107T040000.sql.gz.age'])
        self.assertFalse(flags['dump-20261107T040000.meta.json'])
        self.assertTrue(flags['mysql-bin.000004.gz.age'])

    def test_meta_without_data_file_is_not_sent(self):
        name = self.write_dump('20261107T040000')
        (self.cfg.dumps_dir / name).unlink()
        self.assertEqual(transfer.local_artifacts(self.cfg), [])

    def test_pending_excludes_delivered(self):
        self.write_dump('20261107T040000')
        self.state.mark_sent('dump-20261107T040000.sql.gz.age', NOW)
        self.assertEqual([a.remote_name for a in transfer.pending(self.cfg, self.state)],
                         ['dump-20261107T040000.meta.json'])

    def test_no_directories_yet(self):
        self.assertEqual(transfer.local_artifacts(self.cfg), [])

    def test_oldest_pending_age(self):
        self.assertIsNone(transfer.oldest_pending_age_hours(self.cfg, self.state, NOW))
        self.write_dump('20261107T040000', mtime=NOW.timestamp() - 5 * 3600)
        self.assertAlmostEqual(transfer.oldest_pending_age_hours(self.cfg, self.state, NOW), 5.0, places=1)


class TestCommands(TmpDirTestCase):
    def test_rsync_is_strict_non_interactive_and_targets_the_configured_account(self):
        cmd = transfer.rsync_command(self.cfg, self.dir / 'f.age', key_path=Path('/private/key'))
        self.assertEqual(cmd[0], 'rsync')
        ssh = cmd[cmd.index('-e') + 1]
        self.assertIn('StrictHostKeyChecking=yes', ssh)
        self.assertIn('BatchMode=yes', ssh)
        self.assertIn('UserKnownHostsFile=/kh', ssh)
        self.assertIn('-i ' + str(Path('/private/key')), ssh)
        self.assertEqual(cmd[-1], 'dbbackup@secondary.example:/')

    def test_private_key_copy_is_owned_by_us_with_0600_and_keeps_the_content(self):
        import os, stat, sys
        path = transfer.ensure_private_key(self.cfg)
        self.assertEqual(path, self.cfg.state_dir / 'ssh_key')
        self.assertTrue(path.read_text().startswith('-----BEGIN OPENSSH PRIVATE KEY-----'))
        self.assertTrue(path.read_bytes().endswith(b'\n'))  # ssh rejects keys without a trailing newline
        if sys.platform != 'win32':
            self.assertEqual(stat.S_IMODE(os.stat(path).st_mode), 0o600)

    def test_private_key_copy_is_refreshed_not_stale(self):
        transfer.ensure_private_key(self.cfg)
        self.key_file.write_text('NEW KEY\n')
        self.assertEqual(transfer.ensure_private_key(self.cfg).read_text(), 'NEW KEY\n')

    def test_missing_key_is_a_clear_error(self):
        self.key_file.unlink()
        with self.assertRaises(CommandError) as ctx:
            transfer.ensure_private_key(self.cfg)
        self.assertIn('not readable', str(ctx.exception))

    def test_age_encrypts_to_a_public_recipient_only(self):
        cmd = transfer.encrypt_command(self.cfg, self.dir / 'a', self.dir / 'b')
        self.assertEqual(cmd[:3], ['age', '-r', 'age1testrecipient'])
        self.assertNotIn('-p', cmd)  # never passphrase mode


class TestSend(TmpDirTestCase):
    def setUp(self):
        super().setUp()
        self.fake = FakeRun()
        p = mock.patch.object(transfer, 'run', self.fake)
        p.start()
        self.addCleanup(p.stop)

    def test_sends_everything_in_order_and_marks_it_delivered(self):
        self.write_dump('20261107T040000')
        self.write_binlog('mysql-bin.000004')
        res = transfer.send_pending(self.cfg, self.state, NOW)
        self.assertIsNone(res.failed)
        self.assertEqual(res.sent, ['dump-20261107T040000.sql.gz.age', 'dump-20261107T040000.meta.json',
                                    'mysql-bin.000004.gz.age'])
        self.assertEqual(transfer.pending(self.cfg, self.state), [])
        self.assertEqual(list(self.cfg.outbox_dir.iterdir()), [])  # encrypted temp copies cleaned up

    def test_plaintext_dump_never_goes_to_rsync(self):
        self.write_dump('20261107T040000')
        transfer.send_pending(self.cfg, self.state, NOW)
        sent_paths = [c[-2] for c in self.fake.calls if c[0] == 'rsync']
        self.assertTrue(all(p.endswith('.age') or p.endswith('.meta.json') for p in sent_paths), sent_paths)

    def test_secondary_down_keeps_everything_pending_and_stops_at_first_failure(self):
        self.write_dump('20261107T040000')
        self.write_binlog('mysql-bin.000004')
        self.fake.rsync_fails = True
        res = transfer.send_pending(self.cfg, self.state, NOW)
        self.assertEqual(res.failed, 'dump-20261107T040000.sql.gz.age')
        self.assertIn('Connection refused', res.error)
        self.assertEqual(res.sent, [])
        self.assertEqual(len(transfer.pending(self.cfg, self.state)), 3)
        self.assertEqual(len([c for c in self.fake.calls if c[0] == 'rsync']), 1)  # did not hammer the host

    def test_retry_after_recovery_delivers_without_reencrypting(self):
        self.write_dump('20261107T040000')
        self.fake.rsync_fails = True
        transfer.send_pending(self.cfg, self.state, NOW)
        encrypt_calls = len([c for c in self.fake.calls if c[0] == 'age'])
        self.fake.rsync_fails = False
        res = transfer.send_pending(self.cfg, self.state, NOW)
        self.assertIsNone(res.failed)
        self.assertEqual(len(res.sent), 2)
        self.assertEqual(len([c for c in self.fake.calls if c[0] == 'age']), encrypt_calls)  # reused the outbox copy
        self.assertEqual(transfer.pending(self.cfg, self.state), [])

    def test_partial_progress_is_remembered(self):
        self.write_dump('20261107T040000')
        self.write_binlog('mysql-bin.000004')
        outcomes = iter([False, False, True])  # dump data ok, meta ok, binlog fails

        def flaky(cmd, **kw):
            if cmd[0] == 'rsync' and next(outcomes):
                raise CommandError('network dropped')
            return self.fake(cmd, **kw)
        with mock.patch.object(transfer, 'run', flaky):
            res = transfer.send_pending(self.cfg, self.state, NOW)
        self.assertEqual(res.failed, 'mysql-bin.000004.gz.age')
        self.assertEqual([a.remote_name for a in transfer.pending(self.cfg, self.state)], ['mysql-bin.000004.gz.age'])

    def test_encryption_failure_is_reported_and_nothing_is_sent(self):
        self.write_dump('20261107T040000')
        self.fake.age_fails = True
        res = transfer.send_pending(self.cfg, self.state, NOW)
        self.assertEqual(res.failed, 'dump-20261107T040000.sql.gz.age')
        self.assertEqual([c for c in self.fake.calls if c[0] == 'rsync'], [])
        self.assertEqual(list(self.cfg.outbox_dir.glob('*.age')), [])

    def test_unreadable_ssh_key_keeps_everything_pending_with_a_clear_error(self):
        self.write_dump('20261107T040000')
        self.key_file.unlink()
        res = transfer.send_pending(self.cfg, self.state, NOW)
        self.assertEqual(res.failed, 'dump-20261107T040000.sql.gz.age')
        self.assertIn('not readable', res.error)
        self.assertEqual(self.fake.calls, [])
        self.assertEqual(len(transfer.pending(self.cfg, self.state)), 2)

    def test_rsync_uses_the_private_copy_of_the_key(self):
        self.write_dump('20261107T040000')
        transfer.send_pending(self.cfg, self.state, NOW)
        rsync = [c for c in self.fake.calls if c[0] == 'rsync'][0]
        self.assertIn('-i ' + str(self.cfg.state_dir / 'ssh_key'), rsync[rsync.index('-e') + 1])

    def test_disabled_without_remote_configuration(self):
        cfg = self.cfg.__class__(**{**self.cfg.__dict__, 'remote_host': ''})
        self.write_dump('20261107T040000')
        res = transfer.send_pending(cfg, self.state, NOW)
        self.assertEqual((res.sent, res.failed), ([], None))
        self.assertEqual(self.fake.calls, [])


if __name__ == '__main__':
    unittest.main()
