"""Helpers for the resilience tests: restart real services, run Celery workers that tests can stop/kill/start."""
import datetime
import json
import os
import subprocess
import sys
import time

import pytest
import redis

from tests.config_test import getUrl
from tests.configure_local_base import configure
from tests.integration.services.conftest import TEST_ENV, compose
from tests.integration.services.config_integration import (build_app, db_query, delete_test_locals, mint_admin_token,
                                                           redis_client, remove_public_folders)

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_WORKER = 'tests.integration.services.worker_app.celery'
FLAKY_WORKER = 'tests.integration.services.worker_app_flaky.celery'


def wait_until(predicate, timeout=60, interval=0.5):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if predicate():
                return True
        except Exception:
            pass
        time.sleep(interval)
    return False


def redis_answers():
    return redis_client().ping()


def db_answers():
    return db_query('SELECT 1')[0][0] == 1


def restart_service(name, ready):
    """`docker compose restart` (SIGTERM + start, container filesystem kept) and wait until the service answers."""
    compose('restart', name)
    assert wait_until(ready, timeout=120), f'{name} did not come back after the restart'


def flush_broker():
    """Drop whatever a previous test left in the Celery broker (Redis db 1)."""
    from globals import REDIS_HOST, REDIS_PASSWORD, REDIS_PORT
    redis.Redis(host=REDIS_HOST, port=int(REDIS_PORT), password=REDIS_PASSWORD, db=1).flushdb()


class Worker:
    """A real `celery worker` subprocess a test can stop, kill (SIGKILL) and start again."""

    def __init__(self, app_path=DEFAULT_WORKER, env=None, name='resilience'):
        self.app_path = app_path
        self.env = env or {}
        self.log_path = os.path.join(HERE, f'celery-worker-{name}.log')
        self.proc = None

    def start(self, timeout=60):
        env = {**os.environ, **TEST_ENV, 'FLASK_DEBUG': '1', **self.env}
        self._log = open(self.log_path, 'a')
        self.proc = subprocess.Popen(
            [sys.executable, '-m', 'celery', '-A', self.app_path, 'worker', '-Q', 'priority,default', '--pool=solo',
             '--loglevel=info', '--without-gossip', '--without-mingle'],
            env=env, cwd=os.getcwd(), stdout=self._log, stderr=subprocess.STDOUT)
        marker = self.log_text().count('ready.')
        if not wait_until(lambda: self.proc.poll() is None and self.log_text().count('ready.') > marker, timeout):
            self.stop()
            pytest.fail('Celery worker did not become ready:\n' + self.log_text()[-3000:])
        return self

    def log_text(self):
        self._log.flush()
        with open(self.log_path) as log:
            return log.read()

    def stop(self, kill=False):
        if self.proc is None:
            return
        if kill:
            self.proc.kill()
        else:
            self.proc.terminate()
        try:
            self.proc.wait(timeout=20)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.wait()
        self._log.close()
        self.proc = None

    def alive(self):
        return self.proc is not None and self.proc.poll() is None


@pytest.fixture(scope='module')
def app():
    return build_app()


def _assert_equal(a, b):
    assert a == b, f'{a!r} != {b!r}'


@pytest.fixture
def local(app):
    delete_test_locals()
    # SMTP rows are needed for the confirmation email to "send"; booking_timeout keeps new bookings pending.
    seeded = configure(app.test_client(), mint_admin_token(), lambda a, b, *args: _assert_equal(a, b),
                       booking_timeout=60)
    yield seeded
    delete_test_locals(seeded.locals)
    remove_public_folders(seeded.locals)


@pytest.fixture
def worker_factory():
    """Creates workers and guarantees they are stopped (and the broker emptied) whatever the test does."""
    workers = []
    flush_broker()

    def make(**kwargs):
        worker = Worker(name=f'resilience-{len(workers)}', **kwargs)
        workers.append(worker)
        return worker

    yield make
    for worker in workers:
        worker.stop(kill=True)
    flush_broker()


def book(app, local, minutes_from_opening=0):
    day = (datetime.datetime.now() + datetime.timedelta(days=2)).strftime('%Y-%m-%d')
    start = datetime.datetime.strptime(f"{day} {local.timetable[0]['opening_time']}", '%Y-%m-%d %H:%M:%S') \
        + datetime.timedelta(minutes=minutes_from_opening)
    payload = {
        'client_name': 'Client Test',
        'client_tlf': '123456789',
        'client_email': 'client@example.com',
        'datetime_init': start.strftime('%Y-%m-%d %H:%M:%S'),
        'services_ids': [local.services[0]['id']],
        'worker_id': local.workers[0]['id'],
    }
    return app.test_client().post(getUrl('booking', 'local', local.local['id']), data=json.dumps(payload),
                                  content_type='application/json')


def create_pending_booking(app, local, minutes_from_opening=0):
    response = book(app, local, minutes_from_opening)
    assert response.status_code == 201, response.json
    return response.json['booking']['id']


def booking_status(booking_id):
    return db_query('SELECT s.status FROM booking b JOIN status s ON s.id = b.status_id WHERE b.id = %s',
                    (booking_id,))[0][0]


def email_confirmed(booking_id):
    return db_query('SELECT email_confirmed FROM booking WHERE id = %s', (booking_id,))[0][0]


def wait_for_status(booking_id, expected, timeout=45):
    return wait_until(lambda: booking_status(booking_id) == expected, timeout)


def wait_for_email(booking_id, timeout=45):
    return wait_until(lambda: email_confirmed(booking_id), timeout)
