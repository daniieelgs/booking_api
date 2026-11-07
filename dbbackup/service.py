"""Long-running backup service (container entrypoint): ``python3 -m dbbackup.service``."""
from __future__ import annotations

import logging
import signal
import sys
import time
from datetime import datetime
from typing import Optional

from . import binlogs, dump, heartbeat, transfer
from .config import Config, ConfigError
from .scheduler import compute_due
from .state import State
from .util import log

_stop = False


def _handle_signal(signum, frame):
    global _stop
    _stop = True


def run_cycle(cfg: Config, state: State, now: datetime) -> dict:
    """One scheduler tick. Every job is isolated: a failure is recorded and retried later
    but never stops the loop or the other jobs."""
    summary = {'dump': None, 'binlogs': [], 'sent': [], 'errors': []}
    pending_before = transfer.pending(cfg, state)
    due = compute_due(cfg, state, now, len(pending_before))

    if due.dump:
        state.set_dt('last_dump_attempt', now)
        try:
            summary['dump'] = dump.make_dump(cfg, now)
            state.set_dt('last_dump_ok', now)
            state.set_error(None)
            # The dump flushed the logs, so the previous binlog is closed now: archive it
            # right away instead of waiting for the next periodic run.
            due = due.__class__(dump=due.dump, binlogs=True, send=cfg.remote_enabled, heartbeat=due.heartbeat)
        except Exception as e:
            log.error('Dump failed: %s', e)
            state.set_error(f'dump: {e}', now)
            summary['errors'].append(f'dump: {e}')

    if due.binlogs:
        # last_binlog_attempt throttles retries; last_binlog_ship only moves on success,
        # so a persistent failure shows up in the health evaluation.
        state.set_dt('last_binlog_attempt', now)
        try:
            binlogs.flush_binary_logs(cfg)
            summary['binlogs'] = binlogs.archive_new_binlogs(cfg, state)
            state.set_dt('last_binlog_ship', now)
        except Exception as e:
            log.error('Binlog archive failed: %s', e)
            state.set_error(f'binlogs: {e}', now)
            summary['errors'].append(f'binlogs: {e}')

    new_artifacts = bool(summary['dump'] or summary['binlogs'])
    if cfg.remote_enabled and (due.send or new_artifacts):
        state.set_dt('last_send_attempt', now)
        res = transfer.send_pending(cfg, state, now)
        summary['sent'] = res.sent
        if res.sent and res.failed is None:
            state.set_dt('last_send_ok', now)
        if res.failed:
            summary['errors'].append(f'send {res.failed}: {res.error}')
            state.set_error(f'send: {res.error}', now)

    try:
        transfer.prune_local(cfg, state, now)
    except Exception as e:
        log.error('Local pruning failed: %s', e)

    if due.heartbeat or summary['errors']:
        pending_hours = transfer.oldest_pending_age_hours(cfg, state, now)
        healthy, message = heartbeat.evaluate_health(cfg, state, now, pending_hours)
        if due.heartbeat:
            heartbeat.push_kuma(cfg.kuma_push_url, healthy, message)
            state.set_dt('last_heartbeat', now)
        heartbeat.write_status(cfg, state, now, healthy, message, len(transfer.pending(cfg, state)))

    state.save()
    return summary


def main(argv: Optional[list] = None) -> int:
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    try:
        cfg = Config.from_env()
    except ConfigError as e:
        log.error('Configuration error: %s', e)
        return 2

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    cfg.state_dir.mkdir(parents=True, exist_ok=True)
    state = State(cfg.state_dir / 'state.json')
    log.info('Backup service started: db=%s@%s:%s dump=%02d:%02d binlogs every %sh secondary=%s',
             cfg.db_name, cfg.db_host, cfg.db_port, cfg.dump_hour, cfg.dump_minute, cfg.binlog_ship_hours,
             cfg.remote_host or 'DISABLED (local only)')

    while not _stop:
        try:
            run_cycle(cfg, state, datetime.now())
        except Exception as e:  # last line of defence: the loop must survive anything
            log.exception('Unexpected error in backup cycle: %s', e)
        for _ in range(cfg.tick_seconds):
            if _stop:
                break
            time.sleep(1)
    log.info('Backup service stopped')
    return 0


if __name__ == '__main__':
    sys.exit(main())
