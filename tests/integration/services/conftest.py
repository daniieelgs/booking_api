import os
import subprocess
import sys
import time

import pytest

RUN = os.getenv('RUN_INTEGRATION_TESTS') == '1'

TEST_ENV = {
    'DATABASE_NAME': 'bbdd_test',
    'DATABASE_USER': 'test_user',
    'DATABASE_PASS': 'test-pw',
    'DATABASE_HOST': '127.0.0.1',
    'DATABASE_PORT': '3317',
    'REDIS_HOST': '127.0.0.1',
    'REDIS_PORT': '6380',
    'REDIS_PASSWORD': 'test-redis-pw',
    'CELERY_BROKER_URL': 'redis://:test-redis-pw@127.0.0.1:6380/1',
    'CELERY_RESULT_BACKEND': 'redis://:test-redis-pw@127.0.0.1:6380/1',
    'MAX_TIMEOUT_WAIT_BOOKING': '5',
    'HEALTH_CACHE_SECONDS': '0',  # /health must reflect a stopped worker immediately
}

# globals.py binds these at import time and runs load_dotenv(override=True), so they must be in place
# before anything imports it: run this directory on its own (see README.md), never as part of `pytest tests/`.
if RUN:
    os.environ.update(TEST_ENV)

COMPOSE_FILE = os.path.join(os.getcwd(), 'docker', 'docker-compose.test.yml')


def pytest_collection_modifyitems(config, items):
    if RUN:
        return
    skip = pytest.mark.skip(reason='set RUN_INTEGRATION_TESTS=1 and start docker/docker-compose.test.yml (see tests/integration/services/README.md)')
    for item in items:
        if 'services' in item.keywords:
            item.add_marker(skip)


@pytest.fixture(scope='session', autouse=True)
def only_test_services():
    """Refuse to run against anything but the throw-away compose stack (a local .env could override the env)."""
    if not RUN:
        return
    import globals as g
    problems = []
    if str(g.REDIS_PORT) != TEST_ENV['REDIS_PORT'] or g.REDIS_HOST != TEST_ENV['REDIS_HOST']:
        problems.append(f'REDIS {g.REDIS_HOST}:{g.REDIS_PORT}')
    if f"{TEST_ENV['DATABASE_HOST']}:{TEST_ENV['DATABASE_PORT']}/{TEST_ENV['DATABASE_NAME']}" not in g.DATABASE_URI:
        problems.append('DATABASE_URI')
    if problems:
        pytest.exit('Refusing to run: ' + ', '.join(problems) + ' does not point at docker/docker-compose.test.yml '
                    '(is a local .env overriding the test settings?)', returncode=2)


def compose(*args, check=True):
    return subprocess.run(['docker', 'compose', '-f', COMPOSE_FILE, *args], check=check, capture_output=True, text=True)


@pytest.fixture(scope='module')
def celery_worker():
    """Real Celery worker (solo pool) on the same queues as production, against the compose Redis/MariaDB."""
    env = {**os.environ, **TEST_ENV, 'FLASK_DEBUG': '1'}
    log_path = os.path.join(os.getcwd(), 'tests', 'integration', 'services', 'celery-worker.log')
    log_file = open(log_path, 'w')
    proc = subprocess.Popen(
        [sys.executable, '-m', 'celery', '-A', 'tests.integration.services.worker_app.celery', 'worker',
         '-Q', 'priority,default', '--pool=solo', '--loglevel=info', '--without-gossip', '--without-mingle'],
        env=env, cwd=os.getcwd(), stdout=log_file, stderr=subprocess.STDOUT)
    proc.log_path = log_path

    deadline = time.time() + 60
    ready = False
    while time.time() < deadline and proc.poll() is None:
        log_file.flush()
        if 'ready.' in open(log_path).read():
            ready = True
            break
        time.sleep(0.5)

    if not ready:
        proc.terminate()
        log_file.close()
        pytest.fail('Celery worker did not become ready in 60 s:\n' + open(log_path).read()[-3000:])

    yield proc

    proc.terminate()
    try:
        proc.wait(timeout=15)
    except subprocess.TimeoutExpired:
        proc.kill()
    log_file.close()
