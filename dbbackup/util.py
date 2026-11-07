from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

log = logging.getLogger('dbbackup')

# Client binaries. The "mariadb-*" names exist in every MariaDB client from 10.5 on, while the legacy
# "mysql*" aliases were dropped in 11.x (e.g. `mysqlbinlog` is gone), so never use the legacy names.
MYSQL = 'mariadb'
MYSQLDUMP = 'mariadb-dump'
MYSQLBINLOG = 'mariadb-binlog'

# Recent mariadb-dump clients (10.11.x patch releases and 11.x) start every dump with
# "/*M!999999\- enable the sandbox mode */". Servers/clients from 10.5 do not understand "\-" and abort
# with "Unknown command '\-'", so the line is removed: our dumps must load into the 10.5 server.
_SANDBOX_LINE = re.compile(rb'\A/\*M!999999\\-[^\n]*\n')


def strip_sandbox_header(data: bytes) -> bytes:
    return _SANDBOX_LINE.sub(b'', data, count=1)


class CommandError(RuntimeError):
    """An external command failed. The message never contains secrets: passwords
    are always passed through the environment (MYSQL_PWD), never as arguments."""


def run(cmd: Sequence[str], env: Optional[Mapping[str, str]] = None, input_bytes: Optional[bytes] = None,
        timeout: Optional[float] = None, check: bool = True) -> subprocess.CompletedProcess:
    full_env = dict(os.environ)
    if env:
        full_env.update(env)
    try:
        proc = subprocess.run(list(cmd), env=full_env, input=input_bytes, capture_output=True, timeout=timeout)
    except FileNotFoundError:
        raise CommandError(f'{cmd[0]}: command not found')
    except subprocess.TimeoutExpired:
        raise CommandError(f'{cmd[0]}: timed out after {timeout}s')
    if check and proc.returncode != 0:
        stderr = proc.stderr.decode('utf-8', errors='replace')[-2000:].strip()
        raise CommandError(f'{cmd[0]} exited with {proc.returncode}: {stderr}')
    return proc


def run_pipeline(first: Sequence[str], first_env: Optional[Mapping[str, str]],
                 second: Sequence[str], second_env: Optional[Mapping[str, str]]) -> None:
    """Run ``first | second`` and raise CommandError if either side fails."""
    env1 = dict(os.environ); env1.update(first_env or {})
    env2 = dict(os.environ); env2.update(second_env or {})
    import tempfile
    with tempfile.TemporaryFile() as err1, tempfile.TemporaryFile() as err2:
        try:
            p1 = subprocess.Popen(list(first), stdout=subprocess.PIPE, stderr=err1, env=env1)
            p2 = subprocess.Popen(list(second), stdin=p1.stdout, stdout=subprocess.DEVNULL, stderr=err2, env=env2)
        except FileNotFoundError as e:
            raise CommandError(f'command not found: {e.filename}')
        p1.stdout.close()
        rc2 = p2.wait()
        rc1 = p1.wait()
        err1.seek(0); err2.seek(0)
        e1 = err1.read().decode('utf-8', errors='replace')[-2000:].strip()
        e2 = err2.read().decode('utf-8', errors='replace')[-2000:].strip()
    if rc1 != 0:
        raise CommandError(f'{first[0]} exited with {rc1}: {e1}')
    if rc2 != 0:
        raise CommandError(f'{second[0]} exited with {rc2}: {e2}')


def sha256_file(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        while True:
            block = f.read(chunk)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


def atomic_write_json(path: Path, data: Any) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.tmp')
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, sort_keys=True)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def read_json(path: Path, default: Any = None) -> Any:
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def iso(dt: datetime) -> str:
    return dt.replace(microsecond=0).isoformat()


def parse_iso(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def mysql_env(password: str) -> dict:
    return {'MYSQL_PWD': password}


def client_args(host: str, port: int, user: str) -> list:
    return ['-h', host, '-P', str(port), '-u', user, '--protocol=TCP']
