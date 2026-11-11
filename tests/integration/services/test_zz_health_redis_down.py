"""Stops the shared Redis container on purpose: keep this file last (zz) and out of any parallel run."""
import time

import pytest

from helpers.Database import ping_redis
from tests.integration.services.config_integration import build_app
from tests.integration.services.conftest import compose

pytestmark = pytest.mark.services


def wait_until(predicate, timeout=60, interval=1):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return False


def test_health_reports_error_when_redis_goes_down_and_recovers(celery_worker):
    client = build_app().test_client()
    assert client.get('/health').json == {'status': 'ok'}

    compose('stop', 'redis')
    try:
        response = client.get('/health')

        assert response.status_code == 200
        assert response.json == {'status': 'error'}
        assert ping_redis() is False
    finally:
        compose('up', '-d', '--wait', 'redis')

    assert wait_until(ping_redis), 'Redis did not come back after restart'
    # the worker has to reconnect to the restarted broker before it answers the ping again
    assert wait_until(lambda: client.get('/health').json == {'status': 'ok'}), client.get('/health').json
