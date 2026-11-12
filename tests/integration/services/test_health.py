import pytest

from tests.integration.services.config_integration import build_app

pytestmark = pytest.mark.services


@pytest.fixture(scope='module')
def client():
    return build_app().test_client()


def test_health_is_ok_with_database_redis_and_worker_running(client, celery_worker):
    response = client.get('/health')

    assert response.status_code == 200
    assert response.json == {'status': 'ok'}


def test_version_endpoint_answers(client):
    response = client.get('/version')

    assert response.status_code == 200
    assert 'version' in response.json
