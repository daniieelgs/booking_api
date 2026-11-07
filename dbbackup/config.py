from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Optional


class ConfigError(ValueError):
    pass


def _int(env: Mapping[str, str], name: str, default: int, minimum: int = 0, maximum: Optional[int] = None) -> int:
    raw = env.get(name)
    if raw is None or raw == '':
        return default
    try:
        value = int(raw)
    except ValueError:
        raise ConfigError(f'{name} must be an integer, got {raw!r}')
    if value < minimum or (maximum is not None and value > maximum):
        raise ConfigError(f'{name}={value} is out of range')
    return value


def _float(env: Mapping[str, str], name: str, default: float) -> float:
    raw = env.get(name)
    if raw is None or raw == '':
        return default
    try:
        value = float(raw)
    except ValueError:
        raise ConfigError(f'{name} must be a number, got {raw!r}')
    if value <= 0:
        raise ConfigError(f'{name} must be > 0')
    return value


@dataclass(frozen=True)
class Config:
    # Database (a dedicated, least-privilege user; never the root account)
    db_host: str
    db_port: int
    db_name: str
    db_user: str
    db_password: str

    # Local storage
    backup_dir: str = '/backups'

    # Schedule
    dump_hour: int = 4
    dump_minute: int = 0
    dump_retry_minutes: int = 30
    binlog_ship_hours: float = 6.0
    send_retry_minutes: int = 15
    heartbeat_minutes: int = 5
    tick_seconds: int = 30

    # Local retention
    local_keep_dumps: int = 2
    local_binlog_days: int = 7
    max_unsent_dumps: int = 7

    # Secondary server (all optional: without them backups stay local only)
    age_recipient: str = ''
    remote_host: str = ''
    remote_port: int = 22
    remote_user: str = 'dbbackup'
    remote_path: str = '/'
    ssh_key_file: str = '/run/secrets/backup_ssh_key'
    ssh_known_hosts_file: str = '/run/secrets/backup_known_hosts'

    # Monitoring
    kuma_push_url: str = ''
    stale_dump_hours: int = 26
    stale_pending_hours: int = 24

    @property
    def dumps_dir(self) -> Path:
        return Path(self.backup_dir) / 'dumps'

    @property
    def binlogs_dir(self) -> Path:
        return Path(self.backup_dir) / 'binlogs'

    @property
    def state_dir(self) -> Path:
        return Path(self.backup_dir) / 'state'

    @property
    def outbox_dir(self) -> Path:
        return self.state_dir / 'outbox'

    @property
    def restore_dir(self) -> Path:
        return Path(self.backup_dir) / 'restore'

    @property
    def remote_enabled(self) -> bool:
        return bool(self.remote_host and self.age_recipient)

    @classmethod
    def from_env(cls, env: Optional[Mapping[str, str]] = None) -> 'Config':
        env = os.environ if env is None else env

        missing = [n for n in ('DB_NAME', 'DB_USER', 'DB_PASSWORD') if not env.get(n)]
        if missing:
            raise ConfigError('Missing required environment variables: ' + ', '.join(missing))

        return cls(
            db_host=env.get('DB_HOST', 'database'),
            db_port=_int(env, 'DB_PORT', 3306, 1, 65535),
            db_name=env['DB_NAME'],
            db_user=env['DB_USER'],
            db_password=env['DB_PASSWORD'],
            backup_dir=env.get('BACKUP_DIR', '/backups'),
            dump_hour=_int(env, 'DUMP_HOUR', 4, 0, 23),
            dump_minute=_int(env, 'DUMP_MINUTE', 0, 0, 59),
            dump_retry_minutes=_int(env, 'DUMP_RETRY_MINUTES', 30, 1),
            binlog_ship_hours=_float(env, 'BINLOG_SHIP_HOURS', 6.0),
            send_retry_minutes=_int(env, 'SEND_RETRY_MINUTES', 15, 1),
            heartbeat_minutes=_int(env, 'HEARTBEAT_MINUTES', 5, 1),
            tick_seconds=_int(env, 'TICK_SECONDS', 30, 1),
            local_keep_dumps=_int(env, 'LOCAL_KEEP_DUMPS', 2, 1),
            local_binlog_days=_int(env, 'LOCAL_BINLOG_DAYS', 7, 1),
            max_unsent_dumps=_int(env, 'MAX_UNSENT_DUMPS', 7, 1),
            age_recipient=env.get('AGE_RECIPIENT', ''),
            remote_host=env.get('REMOTE_HOST', ''),
            remote_port=_int(env, 'REMOTE_PORT', 22, 1, 65535),
            remote_user=env.get('REMOTE_USER', 'dbbackup'),
            remote_path=env.get('REMOTE_PATH', '/'),
            ssh_key_file=env.get('SSH_KEY_FILE', '/run/secrets/backup_ssh_key'),
            ssh_known_hosts_file=env.get('SSH_KNOWN_HOSTS_FILE', '/run/secrets/backup_known_hosts'),
            kuma_push_url=env.get('KUMA_PUSH_URL', ''),
            stale_dump_hours=_int(env, 'STALE_DUMP_HOURS', 26, 1),
            stale_pending_hours=_int(env, 'STALE_PENDING_HOURS', 24, 1),
        )
