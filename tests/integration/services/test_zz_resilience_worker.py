"""The Celery worker going away and coming back, and an SMTP outage with real retries."""
import os
import tempfile

import pytest

from tests.integration.services.resilience_support import (FLAKY_WORKER, app, booking_status, create_pending_booking,  # noqa: F401
                                                           email_confirmed, local, wait_for_email, wait_for_status,
                                                           wait_until, worker_factory)

pytestmark = [pytest.mark.services, pytest.mark.resilience]


@pytest.mark.parametrize('kill', [False, True], ids=['graceful-stop', 'sigkill'])
def test_tasks_queued_while_the_worker_is_down_run_when_it_starts_again(app, local, worker_factory, kill):
    from celery_app.tasks import check_booking_status
    worker = worker_factory().start()
    worker.stop(kill=kill)
    bookings = [create_pending_booking(app, local, 240 * i) for i in range(2)]
    for booking_id in bookings:
        check_booking_status.delay(booking_id)
    assert all(booking_status(b) == 'P' for b in bookings)

    worker.start()

    for booking_id in bookings:
        assert wait_for_status(booking_id, 'X'), f'booking {booking_id} was not processed after the worker restart'


def test_confirmation_email_is_retried_until_smtp_recovers(app, local, worker_factory):
    from celery_app.tasks import send_mail_task
    from globals import EmailType
    attempts_file = os.path.join(tempfile.mkdtemp(), 'attempts')
    worker = worker_factory(app_path=FLAKY_WORKER, env={
        'FLAKY_SMTP_ATTEMPTS_FILE': attempts_file, 'FLAKY_SMTP_FAIL_TIMES': '2',
        # default_retry_delay = 60 * RETRY_SEND_EMAIL seconds: 0 retries straight away instead of after 2 h
        'RETRY_SEND_EMAIL': '0'}).start()
    booking_id = create_pending_booking(app, local)
    assert email_confirmed(booking_id) in (0, None, False)

    send_mail_task.delay(local.local['id'], booking_id, int(EmailType.CONFIRMED_EMAIL))

    assert wait_for_email(booking_id), 'email was never delivered:\n' + worker.log_text()[-2500:]
    with open(attempts_file) as f:
        assert len(f.readlines()) == 3  # two simulated SMTP failures, then success
