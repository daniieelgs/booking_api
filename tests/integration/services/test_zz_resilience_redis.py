"""Redis restarts under a running API and a running worker. Restarts the shared container: keep serial."""
import pytest

from tests.integration.services.resilience_support import (app, book, booking_status, create_pending_booking,  # noqa: F401
                                                           email_confirmed, local, redis_answers, restart_service,
                                                           wait_for_email, wait_for_status, worker_factory)

pytestmark = [pytest.mark.services, pytest.mark.resilience]


def test_api_keeps_booking_after_redis_restarts_without_restarting_the_api(app, local):
    assert book(app, local, 0).status_code == 201

    restart_service('redis', redis_answers)

    response = book(app, local, 240)
    assert response.status_code == 201, (response.status_code, response.json)


def test_worker_keeps_consuming_after_redis_restarts(app, local, worker_factory):
    from celery_app.tasks import check_booking_status
    worker = worker_factory().start()
    before = create_pending_booking(app, local, 0)
    check_booking_status.delay(before)
    assert wait_for_status(before, 'X'), 'worker does not work even before the restart'

    restart_service('redis', redis_answers)

    after = create_pending_booking(app, local, 240)
    check_booking_status.delay(after)
    assert wait_for_status(after, 'X', timeout=90), \
        'the worker (or the producer) did not recover from the Redis restart:\n' + worker.log_text()[-2000:]


def test_email_queued_while_worker_is_down_survives_a_redis_restart(app, local, worker_factory):
    """Relies on the AOF that docker-compose.test.yml enables exactly like production."""
    from celery_app.tasks import send_mail_task
    from globals import EmailType
    booking_id = create_pending_booking(app, local)
    send_mail_task.delay(local.local['id'], booking_id, int(EmailType.CONFIRMED_EMAIL))
    assert _queue_length('priority') == 1

    restart_service('redis', redis_answers)

    assert _queue_length('priority') == 1, 'the queued email was lost when Redis restarted'
    worker_factory().start()
    assert wait_for_email(booking_id), 'queued email was not delivered after Redis restarted'


def _queue_length(name):
    import redis
    from globals import REDIS_HOST, REDIS_PASSWORD, REDIS_PORT
    return redis.Redis(host=REDIS_HOST, port=int(REDIS_PORT), password=REDIS_PASSWORD, db=1).llen(name)
