
import threading
import time

from globals import TIMEOUT_CONFIRM_BOOKING


def check_booking_status(booking_id, timeout):
    print(f'Checking booking status [{booking_id}]...')
    time.sleep(timeout*60)
    print('Booking status checked!')

def start_waiter_booking_status(booking_id, timeout=TIMEOUT_CONFIRM_BOOKING):
    
    thread = threading.Thread(target=check_booking_status, args=(booking_id,timeout,))
    thread.start()
    
    return timeout