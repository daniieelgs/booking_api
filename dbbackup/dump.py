from __future__ import annotations

import gzip
import os
import re
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional, Sequence, Tuple

from .config import Config
from .util import (MYSQLDUMP, CommandError, atomic_write_json, client_args, iso, log, mysql_env, sha256_file,
                   strip_sandbox_header)

HEAD_BYTES = 64 * 1024
TAIL_BYTES = 4096
POS_RE = re.compile(r"CHANGE MASTER TO MASTER_LOG_FILE='([^']+)', MASTER_LOG_POS=(\d+)")
DUMP_NAME_RE = re.compile(r'^dump-(\d{8}T\d{6})\.sql\.gz$')


class DumpError(RuntimeError):
    pass


def dump_command(cfg: Config) -> list:
    """Hot, non-blocking dump of the application database.

    --single-transaction: consistent InnoDB snapshot without locking tables.
    --master-data=2:      records the binlog file/position as a comment so the
                          binary logs can be replayed on top of this dump.
    --flush-logs:         starts a fresh binlog, which keeps the position tidy.
    """
    return [MYSQLDUMP, *client_args(cfg.db_host, cfg.db_port, cfg.db_user),
            '--single-transaction', '--quick', '--master-data=2', '--flush-logs',
            '--routines', '--events', '--triggers', '--hex-blob',
            '--default-character-set=utf8mb4', '--databases', cfg.db_name]


def parse_binlog_position(text: str) -> Optional[Tuple[str, int]]:
    m = POS_RE.search(text)
    if not m:
        return None
    return m.group(1), int(m.group(2))


def dump_stamp(name: str) -> Optional[str]:
    m = DUMP_NAME_RE.match(name)
    return m.group(1) if m else None


def make_dump(cfg: Config, now: datetime, cmd: Optional[Sequence[str]] = None, env: Optional[dict] = None) -> dict:
    """Run the dump, compress it on the fly and write ``dump-<stamp>.sql.gz`` plus
    ``dump-<stamp>.meta.json`` into the dumps directory. Returns the metadata.

    The file only appears under its final name once the dump is complete and
    verified, so a crash never leaves something that looks like a valid backup.
    """
    cfg.dumps_dir.mkdir(parents=True, exist_ok=True)
    stamp = now.strftime('%Y%m%dT%H%M%S')
    name = f'dump-{stamp}.sql.gz'
    final = cfg.dumps_dir / name
    partial = cfg.dumps_dir / (name + '.partial')
    meta_path = cfg.dumps_dir / f'dump-{stamp}.meta.json'

    cmd = list(cmd) if cmd is not None else dump_command(cfg)
    full_env = dict(os.environ)
    full_env.update(env if env is not None else mysql_env(cfg.db_password))

    head = b''
    tail = b''
    try:
        with tempfile.TemporaryFile() as errf:
            try:
                proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=errf, env=full_env)
            except FileNotFoundError:
                raise CommandError(f'{cmd[0]}: command not found')
            with gzip.open(partial, 'wb', compresslevel=6) as gz:
                first = True
                while True:
                    chunk = proc.stdout.read(1 << 20)
                    if not chunk:
                        break
                    if first:
                        chunk = strip_sandbox_header(chunk)
                        first = False
                    if len(head) < HEAD_BYTES:
                        head += chunk[:HEAD_BYTES - len(head)]
                    tail = (tail + chunk)[-TAIL_BYTES:]
                    gz.write(chunk)
            proc.stdout.close()
            rc = proc.wait()
            errf.seek(0)
            err = errf.read().decode('utf-8', errors='replace')[-2000:].strip()

        if rc != 0:
            raise DumpError(f'{cmd[0]} exited with {rc}: {err}')
        if b'-- Dump completed' not in tail:
            raise DumpError('dump looks truncated (no "Dump completed" trailer)')
        position = parse_binlog_position(head.decode('utf-8', errors='replace'))
        if position is None:
            raise DumpError('dump has no binlog position (is log_bin enabled on the server?)')

        os.replace(partial, final)
    finally:
        if partial.exists():
            partial.unlink()

    meta = {
        'name': name,
        'created': iso(now),
        'database': cfg.db_name,
        'binlog_file': position[0],
        'binlog_pos': position[1],
        'size': final.stat().st_size,
        'sha256': sha256_file(final),
    }
    atomic_write_json(meta_path, meta)
    log.info('Dump %s done (%d bytes, binlog %s:%d)', name, meta['size'], position[0], position[1])
    return meta


def list_dumps(dumps_dir: Path) -> list:
    """Complete dumps (data file and meta present), oldest first: [(meta_dict, data_path)]."""
    from .util import read_json
    result = []
    for meta_path in sorted(Path(dumps_dir).glob('dump-*.meta.json')):
        meta = read_json(meta_path)
        if not isinstance(meta, dict) or 'name' not in meta:
            continue
        data = Path(dumps_dir) / meta['name']
        if data.exists():
            result.append((meta, data))
    return result
