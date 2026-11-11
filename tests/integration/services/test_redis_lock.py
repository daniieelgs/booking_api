import threading
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest

from helpers.BookingController import perform_atomic_booking, waitAndRegisterBooking
from helpers.Database import create_redis_connection
from helpers.error.LocalError.LocalOverloadedException import LocalOverloadedException

pytestmark = pytest.mark.services

THREADS = 12
SLOT = '2031-05-05 10:00:00'


@pytest.fixture
def local_id():
    key = f'lock-test-{uuid.uuid4().hex}'
    yield key
    create_redis_connection().delete(key)


def run_concurrently(fn, n=THREADS):
    barrier = threading.Barrier(n)

    def task(i):
        barrier.wait()
        try:
            return fn(i)
        except Exception as e:
            return e

    with ThreadPoolExecutor(max_workers=n) as pool:
        return list(pool.map(task, range(n)))


def test_perform_atomic_booking_lets_exactly_one_contender_win(local_id):
    results = run_concurrently(lambda i: perform_atomic_booking(create_redis_connection(), local_id, SLOT))

    assert results.count(True) == 1, results
    assert results.count(False) == THREADS - 1, results


def test_perform_atomic_booking_stores_the_slot_with_a_ttl(local_id):
    assert perform_atomic_booking(create_redis_connection(), local_id, SLOT, exp=30)

    client = create_redis_connection()
    assert client.get(local_id).decode() == SLOT
    assert 0 < client.ttl(local_id) <= 30


def test_different_slots_of_the_same_local_never_lose_or_duplicate_a_write(local_id):
    slots = [f'2031-05-05 {10 + i}:00:00' for i in range(THREADS)]

    results = run_concurrently(lambda i: perform_atomic_booking(create_redis_connection(), local_id, slots[i]))

    # WATCH makes contenders on the same key retry, so a lost race returns False: the caller loops (see next test).
    assert results.count(True) >= 1
    stored = create_redis_connection().get(local_id).decode().split('|')
    assert len(stored) == results.count(True)
    assert set(stored) <= set(slots)


def test_wait_and_register_serializes_different_slots_of_the_same_local(local_id):
    slots = [f'2031-05-06 {10 + i}:00:00' for i in range(THREADS)]

    results = run_concurrently(lambda i: waitAndRegisterBooking(local_id, slots[i], max_timeout=4, sleep_time=0.01))

    assert all(isinstance(r, str) for r in results), results
    assert sorted(create_redis_connection().get(local_id).decode().split('|')) == sorted(slots)


def test_wait_and_register_same_slot_has_one_winner_and_overloads_the_rest(local_id):
    results = run_concurrently(lambda i: waitAndRegisterBooking(local_id, SLOT, max_timeout=1, sleep_time=0.05))

    winners = [r for r in results if isinstance(r, str)]
    losers = [r for r in results if isinstance(r, LocalOverloadedException)]
    assert len(winners) == 1, results
    assert len(losers) == THREADS - 1, results


def test_locals_do_not_block_each_other():
    ids = [f'lock-test-{uuid.uuid4().hex}' for _ in range(4)]
    try:
        results = run_concurrently(lambda i: perform_atomic_booking(create_redis_connection(), ids[i], SLOT), n=4)
        assert results == [True] * 4
    finally:
        create_redis_connection().delete(*ids)
