import datetime
import json
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from tests.config_test import getUrl
from tests.configure_local_base import configure
from tests.integration.services.config_integration import (build_app, db_query, delete_test_locals, mint_admin_token,
                                                           remove_public_folders)

pytestmark = pytest.mark.services

CONTENDERS = 10


@pytest.fixture(scope='module')
def app():
    return build_app()


@pytest.fixture
def local(app):
    delete_test_locals()
    client = app.test_client()
    seeded = configure(client, mint_admin_token(), lambda a, b, *args: _assert_equal(a, b),
                       booking_timeout=-1, set_smtp_settings=False, set_local_settings=False)
    yield seeded
    delete_test_locals(seeded.locals)
    remove_public_folders(seeded.locals)


def _assert_equal(a, b):
    assert a == b, f'{a!r} != {b!r}'


def booking_payload(local, minutes_from_opening=0, **extra):
    day = (datetime.datetime.now() + datetime.timedelta(days=2)).strftime('%Y-%m-%d')
    start = datetime.datetime.strptime(f"{day} {local.timetable[0]['opening_time']}", '%Y-%m-%d %H:%M:%S') \
        + datetime.timedelta(minutes=minutes_from_opening)
    return {
        'client_name': 'Client Test',
        'client_tlf': '123456789',
        'client_email': 'client@example.com',
        'datetime_init': start.strftime('%Y-%m-%d %H:%M:%S'),
        'services_ids': [local.services[0]['id']],
        'worker_id': local.workers[0]['id'],
        **extra,
    }


def post_concurrently(app, local, payloads):
    barrier = threading.Barrier(len(payloads))

    def post(payload):
        client = app.test_client()
        barrier.wait()
        return client.post(getUrl('booking', 'local', local.local['id']), data=json.dumps(payload),
                           content_type='application/json')

    with ThreadPoolExecutor(max_workers=len(payloads)) as pool:
        return list(pool.map(post, payloads))


def active_bookings(worker_id, datetime_init):
    return db_query(
        "SELECT COUNT(*) FROM booking b JOIN status s ON s.id = b.status_id "
        "WHERE b.worker_id = %s AND b.datetime_init = %s AND s.status IN ('C', 'P')",
        (worker_id, datetime_init))[0][0]


def test_same_worker_and_slot_is_booked_exactly_once(app, local):
    payload = booking_payload(local)

    responses = post_concurrently(app, local, [payload] * CONTENDERS)

    statuses = sorted(r.status_code for r in responses)
    assert statuses.count(201) == 1, statuses
    assert all(code in (409, 503) for code in statuses if code != 201), statuses
    assert active_bookings(payload['worker_id'], payload['datetime_init']) == 1


def test_different_slots_for_the_same_worker_are_all_booked(app, local):
    payloads = [booking_payload(local, minutes_from_opening=30 * i) for i in range(5)]

    responses = post_concurrently(app, local, payloads)

    assert [r.status_code for r in responses] == [201] * 5, [(r.status_code, r.json) for r in responses]
    for payload in payloads:
        assert active_bookings(payload['worker_id'], payload['datetime_init']) == 1


def test_different_workers_can_take_the_same_slot(app, local):
    payloads = [booking_payload(local, worker_id=worker['id']) for worker in local.workers
                if local.work_groups[0]['id'] in worker['work_groups']]
    assert len(payloads) >= 2

    responses = post_concurrently(app, local, payloads)

    assert [r.status_code for r in responses] == [201] * len(payloads), [(r.status_code, r.json) for r in responses]
