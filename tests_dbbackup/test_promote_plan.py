import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from dbbackup import promote_plan
from dbbackup.promote_plan import PlanError


class TestPromotePlan(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.d = Path(self._tmp.name)

    def dump(self, stamp, binlog_seq, pos=4, meta=True, data=True):
        if data:
            (self.d / f'dump-{stamp}.sql.gz.age').write_bytes(b'x')
        if meta:
            (self.d / f'dump-{stamp}.meta.json').write_text(json.dumps({
                'binlog_file': f'mysql-bin.{binlog_seq:06d}', 'binlog_pos': pos, 'database': 'bbdd',
                'created': f'{stamp[:4]}-{stamp[4:6]}-{stamp[6:8]}T04:00:00'}))

    def binlog(self, seq):
        (self.d / f'mysql-bin.{seq:06d}.gz.age').write_bytes(b'x')

    def test_picks_the_newest_complete_dump(self):
        self.dump('20261105T040000', 10)
        self.dump('20261106T040000', 20)
        self.dump('20261107T040000', 30, meta=False)  # transfer interrupted: not usable
        plan = promote_plan.build_plan(self.d)
        self.assertEqual(plan['data'], 'dump-20261106T040000.sql.gz.age')
        self.assertEqual(plan['binlog_file'], 'mysql-bin.000020')

    def test_collects_binlogs_from_the_dump_position_onward_in_order(self):
        self.dump('20261106T040000', 20, pos=328)
        for seq in (18, 19, 20, 21, 22):
            self.binlog(seq)
        plan = promote_plan.build_plan(self.d)
        self.assertEqual(plan['binlogs'], ['mysql-bin.000020.gz.age', 'mysql-bin.000021.gz.age', 'mysql-bin.000022.gz.age'])
        self.assertEqual(plan['binlog_pos'], 328)
        self.assertEqual(plan['gaps'], [])

    def test_gaps_in_the_sequence_are_reported(self):
        self.dump('20261106T040000', 20)
        for seq in (20, 22, 25):
            self.binlog(seq)
        self.assertEqual(promote_plan.build_plan(self.d)['gaps'],
                         ['mysql-bin.000021', 'mysql-bin.000023', 'mysql-bin.000024'])

    def test_replay_stops_at_the_first_gap_never_skipping_over_it(self):
        self.dump('20261106T040000', 20)
        for seq in (20, 21, 23, 24):  # 22 is missing: 23 and 24 must NOT be replayed
            self.binlog(seq)
        plan = promote_plan.build_plan(self.d)
        self.assertEqual(plan['binlogs'], ['mysql-bin.000020.gz.age', 'mysql-bin.000021.gz.age'])
        self.assertEqual(plan['gaps'], ['mysql-bin.000022'])

    def test_missing_start_binlog_means_nothing_can_be_replayed(self):
        self.dump('20261106T040000', 20)
        for seq in (21, 22):  # the log the dump position refers to (20) never arrived
            self.binlog(seq)
        plan = promote_plan.build_plan(self.d)
        self.assertEqual(plan['binlogs'], [])
        self.assertEqual(plan['gaps'], ['mysql-bin.000020'])

    def test_dump_only_no_binlogs_is_a_valid_plan(self):
        self.dump('20261106T040000', 20)
        plan = promote_plan.build_plan(self.d)
        self.assertEqual((plan['binlogs'], plan['gaps']), ([], []))

    def test_other_binlog_basenames_are_ignored(self):
        self.dump('20261106T040000', 20)
        (self.d / 'other-bin.000021.gz.age').write_bytes(b'x')
        self.assertEqual(promote_plan.build_plan(self.d)['binlogs'], [])

    def test_no_dump_at_all(self):
        with self.assertRaises(PlanError):
            promote_plan.build_plan(self.d)

    def test_corrupt_meta(self):
        self.dump('20261106T040000', 20)
        (self.d / 'dump-20261106T040000.meta.json').write_text('{oops')
        with self.assertRaises(PlanError):
            promote_plan.build_plan(self.d)

    def test_shell_output_is_evaluable_and_quotes_hostile_names(self):
        self.dump('20261106T040000', 20, pos=328)
        self.binlog(20)
        out = promote_plan.to_shell(promote_plan.build_plan(self.d))
        script = out + '\necho "$PLAN_DUMP|$PLAN_BINLOG_FILE|$PLAN_BINLOG_POS|${PLAN_BINLOGS[0]}|${#PLAN_GAPS[@]}"'
        if shutil.which('bash') is None:
            self.skipTest('bash not available')
        # via stdin: multi-line "-c" arguments get mangled by some Windows bash launchers
        # bytes, not text: text mode would turn "\n" into "\r\n" on Windows
        res = subprocess.run(['bash'], input=script.encode(), capture_output=True)
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual(res.stdout.decode().strip(),
                         'dump-20261106T040000.sql.gz.age|mysql-bin.000020|328|mysql-bin.000020.gz.age|0')

    def test_cli(self):
        self.assertEqual(promote_plan.main(['--dir', str(self.d)]), 1)
        self.dump('20261106T040000', 20)
        self.assertEqual(promote_plan.main(['--dir', str(self.d)]), 0)
        self.assertEqual(promote_plan.main(['--dir', str(self.d / 'missing')]), 1)


if __name__ == '__main__':
    unittest.main()
