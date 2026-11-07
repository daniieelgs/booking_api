from __future__ import annotations

import gzip
import os
import re
import shutil
import tempfile
from pathlib import Path
from typing import List

from .config import Config
from .state import State
from .util import MYSQL, MYSQLBINLOG, CommandError, client_args, log, mysql_env, run

BINLOG_RE = re.compile(r'^(?P<base>.+)\.(?P<seq>\d{6})$')


def binlog_seq(name: str) -> int:
    m = BINLOG_RE.match(name)
    if not m:
        raise ValueError(f'not a binlog name: {name!r}')
    return int(m.group('seq'))


def parse_show_binary_logs(output: str) -> List[str]:
    """Parse ``mysql -N -B -e "SHOW BINARY LOGS"`` (name<TAB>size per line)."""
    names = []
    for line in output.splitlines():
        line = line.strip()
        if not line:
            continue
        names.append(line.split('\t')[0])
    return names


def list_server_binlogs(cfg: Config) -> List[str]:
    proc = run([MYSQL, *client_args(cfg.db_host, cfg.db_port, cfg.db_user), '-N', '-B', '-e', 'SHOW BINARY LOGS'],
               env=mysql_env(cfg.db_password), timeout=60)
    return parse_show_binary_logs(proc.stdout.decode('utf-8', errors='replace'))


def flush_binary_logs(cfg: Config) -> None:
    run([MYSQL, *client_args(cfg.db_host, cfg.db_port, cfg.db_user), '-e', 'FLUSH BINARY LOGS'],
        env=mysql_env(cfg.db_password), timeout=60)


def fetch_and_compress(cfg: Config, name: str) -> Path:
    """Download one closed binlog from the server and store it gzip-compressed."""
    cfg.binlogs_dir.mkdir(parents=True, exist_ok=True)
    final = cfg.binlogs_dir / f'{name}.gz'
    with tempfile.TemporaryDirectory(dir=cfg.binlogs_dir, prefix='.fetch-') as tmp:
        run([MYSQLBINLOG, '--read-from-remote-server', '--raw',
             *client_args(cfg.db_host, cfg.db_port, cfg.db_user),
             f'--result-file={tmp}{os.sep}', name],
            env=mysql_env(cfg.db_password), timeout=600)
        raw = Path(tmp) / name
        if not raw.exists():
            raise CommandError(f'mysqlbinlog produced no file for {name}')
        partial = cfg.binlogs_dir / f'{name}.gz.partial'
        with open(raw, 'rb') as src, gzip.open(partial, 'wb', compresslevel=6) as dst:
            shutil.copyfileobj(src, dst)
        os.replace(partial, final)
    return final


def archive_new_binlogs(cfg: Config, state: State) -> List[str]:
    """Archive every *closed* binlog not archived yet. The last one listed by the
    server is the active file and is skipped (it is still being written)."""
    logs = list_server_binlogs(cfg)
    closed = logs[:-1]
    done = []
    for name in closed:
        if name in state.archived_binlogs:
            continue
        try:
            fetch_and_compress(cfg, name)
        except CommandError as e:
            # Most likely purged by expire_logs_days between listing and fetching.
            log.warning('Could not archive binlog %s: %s', name, e)
            continue
        state.mark_archived(name)
        done.append(name)
        log.info('Archived binlog %s', name)
    return done
