import time

from flask import current_app
from sqlalchemy import text

from db import db
from globals import HEALTH_CACHE_SECONDS, HEALTH_WORKER_TIMEOUT, is_redis_test_mode, log
from helpers.Database import ping_redis

# Status values returned by GET /health, ordered from healthy to worst. Add new ones here and in compute_status.
STATUS_OK = 'ok'
STATUS_DEGRADED = 'degraded'  # API works but background work is not running (worker down: emails are delayed)
STATUS_ERROR = 'error'        # Redis down: bookings (slot lock) and the task queue fail, read-only endpoints work
STATUS_CRITICAL = 'critical'  # Database down: the API cannot serve anything useful

_worker_cache = {'at': 0.0, 'value': None}


def check_database() -> bool:
    try:
        db.session.execute(text('SELECT 1'))
        return True
    except Exception as e:
        log('Health check: database does not answer', level='WARNING', error=e)
        try:
            db.session.rollback()
        except Exception:
            pass
        return False


def check_redis() -> bool:
    return ping_redis()


def _ping_worker() -> bool:
    if is_redis_test_mode():
        return True
    try:
        celery = current_app.extensions.get('celery')
        if celery is None:
            return False
        return bool(celery.control.ping(timeout=HEALTH_WORKER_TIMEOUT, limit=1))
    except Exception as e:
        log('Health check: worker ping failed', level='WARNING', error=e)
        return False


def check_worker() -> bool:
    """Any Celery worker answering a broadcast ping. Cached briefly: with no worker every call would block for the
    ping timeout, which would make a public endpoint a cheap way to tie up the API."""
    now = time.monotonic()
    if _worker_cache['value'] is not None and now - _worker_cache['at'] < HEALTH_CACHE_SECONDS:
        return _worker_cache['value']
    value = _ping_worker()
    _worker_cache.update(at=now, value=value)
    return value


def compute_status(database: bool, redis: bool, worker: bool) -> str:
    if not database:
        return STATUS_CRITICAL
    if not redis:
        return STATUS_ERROR
    if not worker:
        return STATUS_DEGRADED
    return STATUS_OK


def get_health_status() -> str:
    database = check_database()
    redis = check_redis()
    # The worker is reached through Redis: with Redis down it cannot answer, so do not wait for the timeout.
    worker = check_worker() if redis else False
    status = compute_status(database, redis, worker)
    if status != STATUS_OK:
        log(f'Health check: {status} (database={database}, redis={redis}, worker={worker})', level='WARNING')
    return status
