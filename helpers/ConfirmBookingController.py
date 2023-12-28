
import threading
import time


def check_booking_status(booking_id):
    print(f'Checking booking status [{booking_id}]...')
    time.sleep(5)
    print('Booking status checked!')

def start_waiter_booking_status(booking_id):
    thread = threading.Thread(target=check_booking_status, args=(booking_id,))
    thread.start()