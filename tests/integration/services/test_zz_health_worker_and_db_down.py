"""/health states that need a stopped worker or a stopped MariaDB. Stops the shared container: keep serial."""
import pytest

from tests.integration.services.config_integration import build_app
from tests.integration.services.conftest import compose
from tests.integration.services.resilience_support import db_answers, wait_until

pytestmark = pytest.mark.services


@pytest.fixture(scope='module')
def client():
    return build_app().test_client()


def test_health_is_degraded_when_no_worker_is_running(client):
    # no celery_worker fixture here: Redis and MariaDB are up but nobody consumes the queues
    assert client.get('/health').json == {'status': 'degraded'}


def test_health_is_critical_when_mariadb_goes_down_and_recovers(client):
    compose('stop', 'database')
    try:
        response = client.get('/health')

        assert response.status_code == 200
        assert response.json == {'status': 'critical'}
    finally:
        compose('up', '-d', '--wait', 'database')

    assert wait_until(db_answers, timeout=120), 'MariaDB did not come back'
    # still no worker, so "degraded" (not critical) proves the database check recovered by itself
    assert wait_until(lambda: client.get('/health').json == {'status': 'degraded'}), client.get('/health').json
