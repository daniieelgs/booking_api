"""EXPERIMENTS: does Celery+Redis duplicate or lose confirmation emails when a retry waits longer than the broker's
visibility_timeout (VT), or when a worker dies? The worker runs in a Linux container (prefork + event loop, like
production, see docker_worker.py); delays are scaled down (VT of seconds instead of 1 h, retry delay of minutes
instead of 2 h). Redis only re-checks unacknowledged messages about every 100 s, so durations are in minutes.
Results are printed: run with `-s`. Needs the `booking-exp-worker` image (see docker_worker.py)."""
import os
import time

import pytest

from tests.integration.services.docker_worker import DockerWorker
from tests.integration.services.resilience_support import (app, create_pending_booking, email_confirmed, flush_broker,  # noqa: F401
                                                           local, wait_until)

pytestmark = [pytest.mark.services, pytest.mark.resilience]
EXP_DIR = os.path.join(os.getcwd(), 'tests', 'integration', 'services', '.exp')


@pytest.fixture
def exp():
    os.makedirs(EXP_DIR, exist_ok=True)
    flush_broker()
    workers = []
    counter = [0]

    def attempts_file():
        counter[0] += 1
        path = os.path.join(EXP_DIR, f'attempts-{os.getpid()}-{counter[0]}')
        open(path, 'w').close()
        return path

    def start(path, **env):
        name = f'exp-worker-{os.getpid()}-{len(workers)}'
        worker = DockerWorker(name, env={'EXP_ATTEMPTS_FILE': '/app/' + os.path.relpath(path).replace(os.sep, '/'),
                                         **{k: str(v) for k, v in env.items()}}).start()
        workers.append(worker)
        return worker

    yield type('Exp', (), {'attempts_file': staticmethod(attempts_file), 'start': staticmethod(start)})
    for worker in workers:
        worker.remove()
    flush_broker()


def calls(path):
    return len(open(path).readlines())


def send(local, booking_id):
    from celery_app.tasks import send_mail_task
    from globals import EmailType
    send_mail_task.delay(local.local['id'], booking_id, int(EmailType.CONFIRMED_EMAIL))


def test_exp1_retry_waiting_longer_than_visibility_timeout_duplicates_the_email(app, local, exp):
    """1st call fails, the retry waits 180 s with VT=10 s. 2 sender calls = no duplicate; more = duplicated email."""
    path = exp.attempts_file()
    exp.start(path, EXP_FAIL_TIMES=1, EXP_VISIBILITY_TIMEOUT=10, RETRY_SEND_EMAIL=3)
    booking_id = create_pending_booking(app, local)
    send(local, booking_id)

    assert wait_until(lambda: email_confirmed(booking_id), timeout=400, interval=2)
    time.sleep(60)
    print(f'\nEXP1 sender calls = {calls(path)} (2 = no duplicate: 1 failure + 1 success)')
    assert calls(path) == 2


@pytest.mark.parametrize('visibility', [10, 150], ids=['vt10s', 'vt150s'])
def test_exp2_worker_killed_while_holding_a_waiting_retry(app, local, exp, visibility):
    """SIGKILL the worker while it holds the retry (ETA 60 s); start another one; how long until the email goes out."""
    path = exp.attempts_file()
    worker = exp.start(path, EXP_FAIL_TIMES=1, EXP_VISIBILITY_TIMEOUT=visibility, RETRY_SEND_EMAIL=1)
    booking_id = create_pending_booking(app, local)
    send(local, booking_id)
    assert wait_until(lambda: calls(path) == 1, timeout=60), 'first attempt never ran'
    time.sleep(5)  # the retry is now scheduled and held unacknowledged
    worker.kill()
    killed = time.time()
    exp.start(path, EXP_FAIL_TIMES=1, EXP_VISIBILITY_TIMEOUT=visibility, RETRY_SEND_EMAIL=1)

    delivered = wait_until(lambda: email_confirmed(booking_id), timeout=visibility + 330, interval=2)
    print(f'\nEXP2 vt={visibility}s: delivered={delivered} after {time.time() - killed:.0f}s, sender calls={calls(path)}')
    assert delivered


@pytest.mark.parametrize('acks_late', ['0', '1'], ids=['acks_early_default', 'acks_late'])
def test_exp3_worker_killed_in_the_middle_of_the_first_attempt(app, local, exp, acks_late):
    """SIGKILL the worker while it is sending (first attempt sleeps 120 s); start another one."""
    path = exp.attempts_file()
    worker = exp.start(path, EXP_SLOW_FIRST_SECONDS=120, EXP_VISIBILITY_TIMEOUT=10, EXP_ACKS_LATE=acks_late)
    booking_id = create_pending_booking(app, local)
    send(local, booking_id)
    assert wait_until(lambda: calls(path) == 1, timeout=60), 'first attempt never ran'
    worker.kill()
    killed = time.time()
    exp.start(path, EXP_VISIBILITY_TIMEOUT=10, EXP_ACKS_LATE=acks_late)

    delivered = wait_until(lambda: email_confirmed(booking_id), timeout=300, interval=2)
    print(f'\nEXP3 acks_late={acks_late}: delivered={delivered} after {time.time() - killed:.0f}s, sender calls={calls(path)}')
    assert delivered
