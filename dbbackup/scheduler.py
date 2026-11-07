from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from .config import Config
from .state import State


@dataclass(frozen=True)
class Due:
    dump: bool
    binlogs: bool
    send: bool
    heartbeat: bool


def dump_due(cfg: Config, state: State, now: datetime) -> bool:
    """A dump is due once today's scheduled time has passed and no successful dump
    exists since then. Because it compares against the last *success* (persisted),
    a container that was down at 04:00 catches up as soon as it starts, and a failed
    attempt is retried every ``dump_retry_minutes``."""
    target = now.replace(hour=cfg.dump_hour, minute=cfg.dump_minute, second=0, microsecond=0)
    if now < target:
        # Nothing scheduled yet today; still take a first backup if none was ever made.
        return state.get_dt('last_dump_ok') is None and _retry_elapsed(state, 'last_dump_attempt', now, cfg.dump_retry_minutes)
    last_ok = state.get_dt('last_dump_ok')
    if last_ok is not None and last_ok >= target:
        return False
    return _retry_elapsed(state, 'last_dump_attempt', now, cfg.dump_retry_minutes)


def _retry_elapsed(state: State, key: str, now: datetime, minutes: float) -> bool:
    last = state.get_dt(key)
    return last is None or now - last >= timedelta(minutes=minutes)


def compute_due(cfg: Config, state: State, now: datetime, pending_count: int) -> Due:
    return Due(
        dump=dump_due(cfg, state, now),
        binlogs=(_retry_elapsed(state, 'last_binlog_ship', now, cfg.binlog_ship_hours * 60)
                 and _retry_elapsed(state, 'last_binlog_attempt', now, cfg.dump_retry_minutes)),
        send=cfg.remote_enabled and pending_count > 0 and _retry_elapsed(state, 'last_send_attempt', now, cfg.send_retry_minutes),
        heartbeat=_retry_elapsed(state, 'last_heartbeat', now, cfg.heartbeat_minutes),
    )
