from __future__ import annotations

import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from typing import List, Optional, Tuple

from .config import Config
from .state import State
from .util import atomic_write_json, iso, log

STATUS_FILE = 'status.json'


def evaluate_health(cfg: Config, state: State, now: datetime, oldest_pending_hours: Optional[float]) -> Tuple[bool, str]:
    """Returns (healthy, message). Unhealthy conditions are exactly the ones the
    owners care about: no recent dump, copies stuck on the primary, binlogs not shipped."""
    problems: List[str] = []

    last_ok = state.get_dt('last_dump_ok')
    if last_ok is None:
        problems.append('no successful dump yet')
    elif now - last_ok > timedelta(hours=cfg.stale_dump_hours):
        problems.append(f'last dump is {int((now - last_ok).total_seconds() // 3600)}h old')

    last_ship = state.get_dt('last_binlog_ship')
    if last_ship is None:
        problems.append('binlogs never archived')
    elif now - last_ship > timedelta(hours=cfg.binlog_ship_hours * 3):
        problems.append(f'binlogs not archived for {int((now - last_ship).total_seconds() // 3600)}h')

    if cfg.remote_enabled and oldest_pending_hours is not None and oldest_pending_hours > cfg.stale_pending_hours:
        problems.append(f'secondary unreachable: oldest undelivered backup is {int(oldest_pending_hours)}h old')

    if problems:
        return False, '; '.join(problems)
    return True, 'OK'


def push_kuma(url: str, ok: bool, message: str, timeout: float = 10.0) -> bool:
    """Uptime Kuma 'push' monitor: GET <url>?status=up|down&msg=...  Never raises."""
    if not url:
        return False
    query = urllib.parse.urlencode({'status': 'up' if ok else 'down', 'msg': message[:200]})
    sep = '&' if '?' in url else '?'
    try:
        with urllib.request.urlopen(f'{url}{sep}{query}', timeout=timeout) as resp:
            return 200 <= resp.status < 300
    except Exception as e:  # network errors must never break the backup loop
        log.warning('Could not push heartbeat to Uptime Kuma: %s', e)
        return False


def write_status(cfg: Config, state: State, now: datetime, healthy: bool, message: str, pending_count: int) -> None:
    atomic_write_json(cfg.state_dir / STATUS_FILE, {
        'updated': iso(now),
        'healthy': healthy,
        'message': message,
        'pending': pending_count,
        'last_dump_ok': state.data.get('last_dump_ok'),
        'last_binlog_ship': state.data.get('last_binlog_ship'),
        'last_send_ok': state.data.get('last_send_ok'),
        'last_error': state.data.get('last_error'),
    })
