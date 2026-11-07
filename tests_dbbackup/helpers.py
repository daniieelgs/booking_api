"""Shared fixtures for the dbbackup tests (stdlib only, no Flask, no database)."""
from __future__ import annotations

import json
import os
import tempfile
import time
import unittest
from datetime import datetime
from pathlib import Path

from dbbackup.config import Config
from dbbackup.state import State
from dbbackup.util import iso

FAKE_DUMP = (
    "-- MariaDB dump 10.19\n"
    "-- CHANGE MASTER TO MASTER_LOG_FILE='mysql-bin.000003', MASTER_LOG_POS=328;\n"
    "CREATE TABLE t (id int primary key);\n"
    "INSERT INTO t VALUES (1);\n"
    "-- Dump completed on 2026-11-07 4:00:03\n"
)


def make_cfg(backup_dir, **overrides) -> Config:
    base = dict(db_host='database', db_port=3306, db_name='bbdd', db_user='backup', db_password='s3cret-pw',
                backup_dir=str(backup_dir), age_recipient='age1testrecipient', remote_host='secondary.example',
                remote_user='dbbackup', remote_path='/', ssh_key_file='/k', ssh_known_hosts_file='/kh')
    base.update(overrides)
    return Config(**base)


class TmpDirTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)
        self.key_file = self.dir / 'mounted_secret_key'
        self.key_file.write_text('-----BEGIN OPENSSH PRIVATE KEY-----\nfake\n-----END OPENSSH PRIVATE KEY-----')
        self.cfg = make_cfg(self.dir, ssh_key_file=str(self.key_file))
        self.cfg.state_dir.mkdir(parents=True, exist_ok=True)
        self.state = State(self.cfg.state_dir / 'state.json')

    def write_dump(self, stamp: str, binlog_file='mysql-bin.000003', pos=328, mtime=None) -> str:
        """Create a complete local dump (data + meta) and return its data file name."""
        self.cfg.dumps_dir.mkdir(parents=True, exist_ok=True)
        name = f'dump-{stamp}.sql.gz'
        data = self.cfg.dumps_dir / name
        data.write_bytes(b'gzdata-' + stamp.encode())
        created = datetime.strptime(stamp, '%Y%m%dT%H%M%S')
        meta = {'name': name, 'created': iso(created), 'database': 'bbdd', 'binlog_file': binlog_file,
                'binlog_pos': pos, 'size': data.stat().st_size, 'sha256': 'x'}
        meta_path = self.cfg.dumps_dir / f'dump-{stamp}.meta.json'
        meta_path.write_text(json.dumps(meta), encoding='utf-8')
        if mtime is not None:
            os.utime(data, (mtime, mtime))
            os.utime(meta_path, (mtime, mtime))
        return name

    def write_binlog(self, name: str, mtime=None) -> Path:
        self.cfg.binlogs_dir.mkdir(parents=True, exist_ok=True)
        p = self.cfg.binlogs_dir / f'{name}.gz'
        p.write_bytes(b'binlog-' + name.encode())
        if mtime is not None:
            os.utime(p, (mtime, mtime))
        return p
