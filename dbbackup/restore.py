"""Recover rows deleted by mistake, without touching the live database.

Flow (``python3 -m dbbackup.restore run --until "YYYY-MM-DD HH:MM:SS"``):

1. take the newest dump created before ``--until``;
2. load it into a throw-away MariaDB (the ``restore-db`` compose service);
3. replay the binary logs on top of it up to ``--until`` (point-in-time recovery);
4. compare primary keys between that reconstructed past and the live database and
   write ``INSERT IGNORE`` statements for every row that exists in the past but is
   missing today.

The live database is only ever read. Applying the generated SQL is a separate,
explicit step done by ``scripts/restore.sh --apply``.

Known limits: only *deleted* rows are recovered (not UPDATEs); rows that were
legitimately deleted after ``--until`` are resurrected too, which is why the SQL is
generated for review first; and the ``before_insert_*`` triggers reset
``datetime_created``/``datetime_updated`` to the moment of re-insertion.
"""
from __future__ import annotations

import argparse
import gzip
import os
import re
import shutil
import sys
import tempfile
import time
from collections import OrderedDict
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

from .binlogs import binlog_seq, list_server_binlogs
from .config import Config, ConfigError
from .dump import list_dumps
from .util import (MYSQL, MYSQLBINLOG, MYSQLDUMP, CommandError, client_args, log, mysql_env, run,
                   run_pipeline, strip_sandbox_header)

IDENT_RE = re.compile(r'^[A-Za-z0-9_$]+$')
SAFE_VALUE_RE = re.compile(r'^[A-Za-z0-9_.:@+\- ]*$')
CHUNK = 500
DATETIME_FMT = '%Y-%m-%d %H:%M:%S'


class RestoreError(RuntimeError):
    pass


# ---------------------------------------------------------------- selection

def parse_until(value: str) -> datetime:
    try:
        return datetime.strptime(value.strip(), DATETIME_FMT)
    except ValueError:
        raise RestoreError(f'--until must look like "2026-11-07 10:31:50", got {value!r}')


def find_base_dump(dumps_dir: Path, until: datetime) -> Tuple[dict, Path]:
    """Newest complete dump created at or before ``until``."""
    best: Optional[Tuple[dict, Path]] = None
    for meta, data in list_dumps(dumps_dir):  # oldest first
        created = datetime.fromisoformat(meta['created'])
        if created <= until:
            best = (meta, data)
    if best is None:
        raise RestoreError(f'No local dump created before {until}. Available: '
                           + (', '.join(m['created'] for m, _ in list_dumps(dumps_dir)) or 'none'))
    return best


def binlogs_from(all_logs: Sequence[str], start_file: str) -> List[str]:
    """Binlogs to replay: ``start_file`` and every later one, in order."""
    if start_file not in all_logs:
        raise RestoreError(
            f'Binlog {start_file} (where the dump starts) no longer exists on the server; '
            f'oldest available is {all_logs[0] if all_logs else "none"}. Use --source archive.')
    return list(all_logs[list(all_logs).index(start_file):])


# ---------------------------------------------------------------- mysql helpers

class Conn:
    def __init__(self, host: str, port: int, user: str, password: str):
        self.host, self.port, self.user, self.password = host, port, user, password

    @property
    def args(self) -> list:
        return client_args(self.host, self.port, self.user)

    @property
    def env(self) -> dict:
        return mysql_env(self.password)

    def query(self, sql: str) -> List[List[str]]:
        proc = run([MYSQL, *self.args, '-N', '-B', '-e', sql], env=self.env, timeout=300)
        out = proc.stdout.decode('utf-8', errors='replace')
        return [line.split('\t') for line in out.splitlines() if line != '']


def _ident(name: str) -> str:
    if not IDENT_RE.match(name):
        raise RestoreError(f'Unsafe identifier {name!r}')
    return name


def list_tables(conn: Conn, db: str) -> List[str]:
    rows = conn.query(f"SELECT TABLE_NAME FROM information_schema.TABLES "
                      f"WHERE TABLE_SCHEMA='{_ident(db)}' AND TABLE_TYPE='BASE TABLE' ORDER BY TABLE_NAME")
    return [r[0] for r in rows]


def pk_columns(conn: Conn, db: str, table: str) -> List[str]:
    rows = conn.query(f"SELECT COLUMN_NAME FROM information_schema.KEY_COLUMN_USAGE "
                      f"WHERE TABLE_SCHEMA='{_ident(db)}' AND TABLE_NAME='{_ident(table)}' "
                      f"AND CONSTRAINT_NAME='PRIMARY' ORDER BY ORDINAL_POSITION")
    return [r[0] for r in rows]


def fetch_keys(conn: Conn, db: str, table: str, cols: Sequence[str]) -> Set[Tuple[str, ...]]:
    sel = ', '.join(f'`{_ident(c)}`' for c in cols)
    rows = conn.query(f'SELECT {sel} FROM `{_ident(db)}`.`{_ident(table)}`')
    return {tuple(r) for r in rows}


def missing_keys(past: Set[Tuple[str, ...]], live: Set[Tuple[str, ...]]) -> List[Tuple[str, ...]]:
    """Keys that existed in the reconstructed past and are gone from the live database."""
    return sorted(past - live)


def _quote(value: str) -> str:
    if not SAFE_VALUE_RE.match(value):
        raise RestoreError(f'Primary key value {value!r} has unexpected characters; refusing to build SQL')
    return "'" + value + "'"


def build_where(cols: Sequence[str], keys: Sequence[Tuple[str, ...]]) -> str:
    if len(cols) == 1:
        return f'`{_ident(cols[0])}` IN (' + ','.join(_quote(k[0]) for k in keys) + ')'
    collist = ','.join(f'`{_ident(c)}`' for c in cols)
    tuples = ','.join('(' + ','.join(_quote(v) for v in k) + ')' for k in keys)
    return f'({collist}) IN ({tuples})'


def chunked(items: Sequence, size: int) -> Iterable[Sequence]:
    for i in range(0, len(items), size):
        yield items[i:i + size]


SQL_HEADER = ('-- Rows recovered by dbbackup.restore. REVIEW before applying.\n'
              'SET FOREIGN_KEY_CHECKS=0;\nSET UNIQUE_CHECKS=0;\nSET AUTOCOMMIT=0;\n')
SQL_FOOTER = 'COMMIT;\nSET FOREIGN_KEY_CHECKS=1;\nSET UNIQUE_CHECKS=1;\n'


def dump_rows_command(scratch: Conn, db: str, table: str, where: str) -> list:
    return [MYSQLDUMP, *scratch.args, '--no-create-info', '--insert-ignore', '--complete-insert',
            '--skip-triggers', '--skip-add-locks', '--skip-comments', '--hex-blob', '--single-transaction',
            f'--where={where}', db, table]


def generate_recovery_sql(scratch: Conn, live: Conn, db: str, out_path: Path,
                          only_tables: Optional[Sequence[str]] = None) -> Dict[str, int]:
    """Write the INSERT IGNORE file and return {table: rows_to_recover}."""
    summary: Dict[str, int] = OrderedDict()
    tables = list_tables(scratch, db)
    if only_tables:
        unknown = set(only_tables) - set(tables)
        if unknown:
            raise RestoreError('Unknown table(s): ' + ', '.join(sorted(unknown)))
        tables = [t for t in tables if t in only_tables]

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as out:
        out.write(SQL_HEADER)
        for table in tables:
            cols = pk_columns(scratch, db, table)
            if not cols:
                log.warning('Table %s has no primary key: skipped', table)
                continue
            past = fetch_keys(scratch, db, table, cols)
            now_keys = fetch_keys(live, db, table, cols)
            lost = missing_keys(past, now_keys)
            summary[table] = len(lost)
            for part in chunked(lost, CHUNK):
                proc = run(dump_rows_command(scratch, db, table, build_where(cols, part)), env=scratch.env, timeout=600)
                out.write(strip_sandbox_header(proc.stdout).decode('utf-8', errors='replace'))
        out.write(SQL_FOOTER)
    return summary


# ---------------------------------------------------------------- scratch DB

def wait_for_db(conn: Conn, timeout: int = 180) -> None:
    deadline = time.time() + timeout
    last = ''
    while time.time() < deadline:
        try:
            conn.query('SELECT 1')
            return
        except CommandError as e:
            last = str(e)
            time.sleep(2)
    raise RestoreError(f'Scratch database not ready after {timeout}s: {last}')


def load_dump(scratch: Conn, dump_path: Path) -> None:
    import subprocess
    env = dict(os.environ); env.update(scratch.env)
    with tempfile.TemporaryFile() as err:
        proc = subprocess.Popen([MYSQL, *scratch.args], stdin=subprocess.PIPE, stderr=err, env=env)
        with gzip.open(dump_path, 'rb') as src:
            shutil.copyfileobj(src, proc.stdin)
        proc.stdin.close()
        rc = proc.wait()
        err.seek(0)
        msg = err.read().decode('utf-8', errors='replace')[-2000:].strip()
    if rc != 0:
        raise RestoreError(f'Loading the dump into the scratch database failed: {msg}')


def mysqlbinlog_command(cfg: Config, files: Sequence[str], start_pos: int, until: Optional[datetime],
                        remote: bool, database: Optional[str], extra: Sequence[str] = ()) -> list:
    cmd = [MYSQLBINLOG]
    if remote:
        cmd += ['--read-from-remote-server', *client_args(cfg.db_host, cfg.db_port, cfg.db_user)]
    cmd += [f'--start-position={start_pos}']
    if until is not None:
        cmd += [f'--stop-datetime={until.strftime(DATETIME_FMT)}']
    if database:
        cmd += [f'--database={database}']
    cmd += list(extra)
    cmd += list(files)
    return cmd


def replay_binlogs(cfg: Config, scratch: Conn, files: Sequence[str], start_pos: int, until: datetime,
                   source: str) -> None:
    if not files:
        return
    if source == 'live':
        cmd = mysqlbinlog_command(cfg, files, start_pos, until, remote=True, database=cfg.db_name)
        run_pipeline(cmd, mysql_env(cfg.db_password), [MYSQL, *scratch.args], scratch.env)
        return
    # archive: decompress the needed files to a temp dir and read them locally
    with tempfile.TemporaryDirectory(prefix='replay-') as tmp:
        paths = []
        for name in files:
            gz = cfg.binlogs_dir / f'{name}.gz'
            if not gz.exists():
                raise RestoreError(f'Archived binlog {name} is missing; replay would have a gap')
            target = Path(tmp) / name
            with gzip.open(gz, 'rb') as src, open(target, 'wb') as dst:
                shutil.copyfileobj(src, dst)
            paths.append(str(target))
        cmd = mysqlbinlog_command(cfg, paths, start_pos, until, remote=False, database=cfg.db_name)
        run_pipeline(cmd, None, [MYSQL, *scratch.args], scratch.env)


def archived_binlogs_from(binlogs_dir: Path, start_file: str) -> List[str]:
    start = binlog_seq(start_file)
    names = []
    for p in sorted(Path(binlogs_dir).glob('*.gz')):
        base = p.name[:-3]
        try:
            if binlog_seq(base) >= start:
                names.append(base)
        except ValueError:
            continue
    return names


# ---------------------------------------------------------------- inspection

TS_RE = re.compile(r'^#(\d{6})\s+(\d{1,2}:\d{2}:\d{2})\s+server id')
ROW_RE = re.compile(r'^### (DELETE FROM|UPDATE|INSERT INTO) `([^`]+)`\.`([^`]+)`')


def summarize_row_events(lines: Iterable[str], ops: Sequence[str] = ('DELETE', 'UPDATE')) -> List[Tuple[str, str, str, int]]:
    """Aggregate decoded row events into (datetime, operation, schema.table, row_count),
    in log order. Input is ``mysqlbinlog -vv --base64-output=DECODE-ROWS`` output."""
    wanted = {o.upper() for o in ops}
    current_ts = ''
    counts: "OrderedDict[Tuple[str, str, str], int]" = OrderedDict()
    for line in lines:
        m = TS_RE.match(line)
        if m:
            d, t = m.groups()
            current_ts = f'20{d[0:2]}-{d[2:4]}-{d[4:6]} {int(t.split(":")[0]):02d}:{t.split(":", 1)[1]}'
            continue
        m = ROW_RE.match(line)
        if m:
            op = {'DELETE FROM': 'DELETE', 'UPDATE': 'UPDATE', 'INSERT INTO': 'INSERT'}[m.group(1)]
            if op in wanted:
                key = (current_ts, op, f'{m.group(2)}.{m.group(3)}')
                counts[key] = counts.get(key, 0) + 1
    return [(ts, op, tbl, n) for (ts, op, tbl), n in counts.items()]


def inspect(cfg: Config, since: Optional[datetime], ops: Sequence[str]) -> int:
    base_until = datetime.now()
    meta, _ = find_base_dump(cfg.dumps_dir, base_until)
    logs = binlogs_from(list_server_binlogs(cfg), meta['binlog_file'])
    cmd = mysqlbinlog_command(cfg, logs, int(meta['binlog_pos']), None, remote=True, database=cfg.db_name,
                              extra=['--base64-output=DECODE-ROWS', '-vv'] +
                                    ([f'--start-datetime={since.strftime(DATETIME_FMT)}'] if since else []))
    proc = run(cmd, env=mysql_env(cfg.db_password), timeout=1800)
    events = summarize_row_events(proc.stdout.decode('utf-8', errors='replace').splitlines(), ops)
    if not events:
        print('No matching row events found.')
        return 0
    print(f'Row events since dump {meta["name"]} (use a time just BEFORE the unwanted one as --until):')
    for ts, op, table, n in events:
        print(f'  {ts}  {op:<6}  {table}  x{n}')
    return 0


# ---------------------------------------------------------------- orchestration

def run_restore(cfg: Config, until: datetime, scratch: Conn, out_path: Path, source: str,
                only_tables: Optional[Sequence[str]]) -> Dict[str, int]:
    meta, dump_path = find_base_dump(cfg.dumps_dir, until)
    log.info('Base dump: %s (created %s, binlog %s:%s)', meta['name'], meta['created'], meta['binlog_file'], meta['binlog_pos'])

    wait_for_db(scratch)
    scratch.query(f'DROP DATABASE IF EXISTS `{_ident(cfg.db_name)}`')
    load_dump(scratch, dump_path)
    log.info('Dump loaded into the scratch database')

    if source == 'live':
        files = binlogs_from(list_server_binlogs(cfg), meta['binlog_file'])
    else:
        files = archived_binlogs_from(cfg.binlogs_dir, meta['binlog_file'])
        if not files or files[0] != meta['binlog_file']:
            raise RestoreError(f'Archive has no binlog {meta["binlog_file"]}; cannot replay from the dump position')
    log.info('Replaying %d binlog file(s) up to %s', len(files), until)
    replay_binlogs(cfg, scratch, files, int(meta['binlog_pos']), until, source)

    live = Conn(cfg.db_host, cfg.db_port, cfg.db_user, cfg.db_password)
    return generate_recovery_sql(scratch, live, cfg.db_name, out_path, only_tables)


def main(argv: Optional[Sequence[str]] = None) -> int:
    logging_setup()
    ap = argparse.ArgumentParser(prog='dbbackup.restore')
    sub = ap.add_subparsers(dest='cmd', required=True)

    p_run = sub.add_parser('run', help='reconstruct the past and generate SQL for the lost rows')
    p_run.add_argument('--until', required=True, help='"YYYY-MM-DD HH:MM:SS", just before the mistake')
    p_run.add_argument('--tables', default='', help='comma separated; default: all tables')
    p_run.add_argument('--source', choices=['live', 'archive'], default='live')
    p_run.add_argument('--out', default='')
    p_run.add_argument('--scratch-host', default=os.environ.get('RESTORE_DB_HOST', 'restore-db'))
    p_run.add_argument('--scratch-port', type=int, default=3306)

    p_ins = sub.add_parser('inspect', help='list DELETE/UPDATE row events to find the right --until')
    p_ins.add_argument('--since', default='')
    p_ins.add_argument('--ops', default='DELETE,UPDATE')

    args = ap.parse_args(argv)
    try:
        cfg = Config.from_env()
        if args.cmd == 'inspect':
            since = parse_until(args.since) if args.since else None
            return inspect(cfg, since, [o.strip() for o in args.ops.split(',') if o.strip()])

        until = parse_until(args.until)
        out = Path(args.out) if args.out else cfg.restore_dir / f'recovered-{datetime.now().strftime("%Y%m%dT%H%M%S")}.sql'
        scratch = Conn(args.scratch_host, args.scratch_port, 'root', os.environ.get('RESTORE_DB_ROOT_PASSWORD', 'restore-scratch'))
        tables = [t.strip() for t in args.tables.split(',') if t.strip()]
        summary = run_restore(cfg, until, scratch, out, args.source, tables or None)
    except (RestoreError, ConfigError, CommandError) as e:
        print(f'ERROR: {e}', file=sys.stderr)
        return 1

    total = sum(summary.values())
    print(f'\nRows missing from the live database but present at {until}:')
    for table, n in summary.items():
        if n:
            print(f'  {table}: {n}')
    print(f'  TOTAL: {total}')
    print(f'SQL written to {out}')
    return 0


def logging_setup() -> None:
    import logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')


if __name__ == '__main__':
    sys.exit(main())
