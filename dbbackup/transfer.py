from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

from .config import Config
from .prune import binlogs_older_than_seq, dumps_to_delete
from .state import State
from .util import CommandError, log, read_json, run


@dataclass(frozen=True)
class Artifact:
    local: Path
    remote_name: str
    encrypt: bool


@dataclass
class SendResult:
    sent: List[str] = field(default_factory=list)
    failed: Optional[str] = None
    error: Optional[str] = None


def local_artifacts(cfg: Config) -> List[Artifact]:
    """Everything that has to reach the secondary, in delivery order.

    For each dump the data file goes first and the meta file last, so the
    receiver never sees a meta without its data (the meta marks a dump complete).
    """
    items: List[Artifact] = []
    if cfg.dumps_dir.exists():
        for meta_path in sorted(cfg.dumps_dir.glob('dump-*.meta.json')):
            meta = read_json(meta_path)
            if not isinstance(meta, dict) or 'name' not in meta:
                continue
            data = cfg.dumps_dir / meta['name']
            if not data.exists():
                continue
            items.append(Artifact(data, meta['name'] + '.age', True))
            items.append(Artifact(meta_path, meta_path.name, False))
    if cfg.binlogs_dir.exists():
        for p in sorted(cfg.binlogs_dir.glob('*.gz')):
            items.append(Artifact(p, p.name + '.age', True))
    return items


def pending(cfg: Config, state: State) -> List[Artifact]:
    return [a for a in local_artifacts(cfg) if a.remote_name not in state.sent]


def oldest_pending_age_hours(cfg: Config, state: State, now: datetime) -> Optional[float]:
    items = pending(cfg, state)
    if not items:
        return None
    oldest = min(a.local.stat().st_mtime for a in items)
    return max(0.0, (now.timestamp() - oldest) / 3600.0)


def encrypt_command(cfg: Config, src: Path, dst: Path) -> list:
    return ['age', '-r', cfg.age_recipient, '-o', str(dst), str(src)]


def private_key_path(cfg: Config) -> Path:
    return cfg.state_dir / 'ssh_key'


def ensure_private_key(cfg: Config) -> Path:
    """OpenSSH refuses a private key that is not owned by the user running it (or has loose
    permissions). The mounted secret belongs to whoever owns it on the host (e.g. uid 1000),
    not to the container user, so it is copied to a private 0600 file before every delivery."""
    src = Path(cfg.ssh_key_file)
    try:
        data = src.read_bytes()
    except OSError as e:
        raise CommandError(f'SSH key {src} is not readable: {e.strerror or e}')
    dst = private_key_path(cfg)
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        dst.unlink()
    fd = os.open(dst, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb') as f:
        f.write(data if data.endswith(b'\n') else data + b'\n')
    return dst


def rsync_command(cfg: Config, src: Path, key_path: Optional[Path] = None) -> list:
    ssh = ' '.join([
        'ssh', '-i', str(key_path or cfg.ssh_key_file), '-p', str(cfg.remote_port),
        '-o', 'BatchMode=yes', '-o', 'IdentitiesOnly=yes',
        '-o', 'StrictHostKeyChecking=yes', '-o', f'UserKnownHostsFile={cfg.ssh_known_hosts_file}',
        '-o', 'ConnectTimeout=15',
    ])
    return ['rsync', '-t', '--timeout=120', '-e', ssh, str(src),
            f'{cfg.remote_user}@{cfg.remote_host}:{cfg.remote_path}']


def send_pending(cfg: Config, state: State, now: datetime) -> SendResult:
    """Deliver every pending artifact. Stops at the first failure (the secondary is
    probably down: no point in hammering it) and leaves the rest for the next retry."""
    result = SendResult()
    if not cfg.remote_enabled:
        return result
    cfg.outbox_dir.mkdir(parents=True, exist_ok=True)

    items = pending(cfg, state)
    if not items:
        return result
    try:
        key_path = ensure_private_key(cfg)
    except CommandError as e:
        result.failed = items[0].remote_name
        result.error = str(e)
        log.warning('Cannot send backups: %s', e)
        return result

    for art in items:
        to_send = art.local
        encrypted: Optional[Path] = None
        try:
            if art.encrypt:
                encrypted = cfg.outbox_dir / art.remote_name
                if not encrypted.exists():
                    tmp = cfg.outbox_dir / (art.remote_name + '.partial')
                    run(encrypt_command(cfg, art.local, tmp), timeout=1800)
                    os.replace(tmp, encrypted)
                to_send = encrypted
            else:
                to_send = art.local
            run(rsync_command(cfg, to_send, key_path), timeout=3600)
        except CommandError as e:
            result.failed = art.remote_name
            result.error = str(e)
            log.warning('Could not send %s (will retry): %s', art.remote_name, e)
            return result

        state.mark_sent(art.remote_name, now)
        result.sent.append(art.remote_name)
        log.info('Sent %s to %s', art.remote_name, cfg.remote_host)
        if encrypted is not None and encrypted.exists():
            encrypted.unlink()
    return result


def prune_local(cfg: Config, state: State, now: datetime) -> List[str]:
    """Local retention: newest ``local_keep_dumps`` dumps plus any dump not yet delivered
    (capped at ``max_unsent_dumps`` so an unreachable secondary cannot fill the disk),
    and binlogs older than ``local_binlog_days`` that were already delivered."""
    deleted: List[str] = []

    if cfg.dumps_dir.exists():
        names = sorted(p.name for p in cfg.dumps_dir.glob('dump-*.sql.gz'))
        unsent = [n for n in names if cfg.remote_enabled and (n + '.age') not in state.sent]
        protected = unsent[-cfg.max_unsent_dumps:]
        for n in dumps_to_delete(names, cfg.local_keep_dumps, protected):
            stamp = n[len('dump-'):-len('.sql.gz')]
            for victim in (cfg.dumps_dir / n, cfg.dumps_dir / f'dump-{stamp}.meta.json'):
                if victim.exists():
                    victim.unlink()
            deleted.append(n)

    if cfg.binlogs_dir.exists():
        limit = now.timestamp() - cfg.local_binlog_days * 86400
        for p in sorted(cfg.binlogs_dir.glob('*.gz')):
            delivered = (not cfg.remote_enabled) or (p.name + '.age') in state.sent
            if delivered and p.stat().st_mtime < limit:
                p.unlink()
                deleted.append(p.name)
        for p in cfg.binlogs_dir.glob('.fetch-*'):
            # Leftovers of an interrupted fetch.
            if p.is_dir() and p.stat().st_mtime < now.timestamp() - 86400:
                import shutil
                shutil.rmtree(p, ignore_errors=True)
    return deleted
