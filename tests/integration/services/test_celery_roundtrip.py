import datetime
import json
import time

import pytest

from tests.config_test import getUrl
from tests.configure_local_base import configure
from tests.integration.services.config_integration import (build_app, db_query, delete_test_locals, mint_admin_token,
                                                           remove_public_folders)

pytestmark = pytest.mark.services


def _assert_equal(a, b):
    assert a == b, f'{a!r} != {b!r}'


@pytest.fixture(scope='module')
def app():
    return build_app()


@pytest.fixture
def local(app):
    delete_test_locals()
    # SMTP rows are needed for the confirmation email to "send", which leaves the booking pending; both the app and
    # the worker run with email_test_mode, so no real SMTP socket is ever opened.
    seeded = configure(app.test_client(), mint_admin_token(), lambda a, b, *args: _assert_equal(a, b),
                       booking_timeout=60)
    yield seeded
    delete_test_locals(seeded.locals)
    remove_public_folders(seeded.locals)


def create_pending_booking(app, local):
    day = (datetime.datetime.now() + datetime.timedelta(days=2)).strftime('%Y-%m-%d')
    payload = {
        'client_name': 'Client Test',
        'client_tlf': '123456789',
        'client_email': 'client@example.com',
        'datetime_init': f"{day} {local.timetable[0]['opening_time']}",
        'services_ids': [local.services[0]['id']],
        'worker_id': local.workers[0]['id'],
    }
    response = app.test_client().post(getUrl('booking', 'local', local.local['id']), data=json.dumps(payload),
                                      content_type='application/json')
    assert response.status_code == 201, response.json
    return response.json['booking']['id']


def booking_status(booking_id):
    return db_query('SELECT s.status FROM booking b JOIN status s ON s.id = b.status_id WHERE b.id = %s',
                    (booking_id,))[0][0]


def test_worker_consumes_a_task_from_the_real_broker_and_updates_mariadb(app, local, celery_worker):
    from celery_app.tasks import check_booking_status

    booking_id = create_pending_booking(app, local)
    assert booking_status(booking_id) == 'P'

    check_booking_status.delay(booking_id)

    deadline = time.time() + 30
    while time.time() < deadline and booking_status(booking_id) == 'P':
        time.sleep(0.5)

    assert booking_status(booking_id) == 'X', 'the worker did not cancel the pending booking'


def test_confirmed_booking_is_left_alone_by_the_worker(app, local, celery_worker):
    from celery_app.tasks import check_booking_status

    booking_id = create_pending_booking(app, local)
    confirm = app.test_client().get(getUrl('booking', 'confirm', booking_id),
                                    headers={'Authorization': f'Bearer {local.refresh_token}'})
    assert confirm.status_code == 200, confirm.json

    task = check_booking_status.delay(booking_id)

    deadline = time.time() + 30
    while time.time() < deadline:
        with open(celery_worker.log_path) as log:
            if f'[{task.id}] succeeded' in log.read():
                break
        time.sleep(0.5)
    else:
        pytest.fail('the worker never reported the task as succeeded')

    assert booking_status(booking_id) == 'C'
