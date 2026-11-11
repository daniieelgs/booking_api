"""MariaDB restarts under a running API and a running worker (stale pooled connections). Keep serial."""
import pytest

from tests.integration.services.resilience_support import (app, book, create_pending_booking, db_answers,  # noqa: F401
                                                           email_confirmed, local, restart_service, wait_for_email,
                                                           worker_factory)

pytestmark = [pytest.mark.services, pytest.mark.resilience]


def test_api_keeps_booking_after_mariadb_restarts_without_restarting_the_api(app, local):
    assert book(app, local, 0).status_code == 201

    restart_service('database', db_answers)

    response = book(app, local, 240)
    assert response.status_code == 201, (response.status_code, response.json)


def test_worker_sends_emails_after_mariadb_restarts_without_restarting_the_worker(app, local, worker_factory):
    from celery_app.tasks import send_mail_task
    from globals import EmailType
    worker = worker_factory().start()
    first = create_pending_booking(app, local, 0)
    send_mail_task.delay(local.local['id'], first, int(EmailType.CONFIRMED_EMAIL))
    assert wait_for_email(first), 'worker does not send emails even before the restart'

    restart_service('database', db_answers)

    second = create_pending_booking(app, local, 240)
    send_mail_task.delay(local.local['id'], second, int(EmailType.CONFIRMED_EMAIL))
    assert wait_for_email(second, timeout=60), \
        'the worker did not recover from the MariaDB restart:\n' + worker.log_text()[-2500:]
