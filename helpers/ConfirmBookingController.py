
import os
import threading
import time

from dotenv import load_dotenv
from db import deleteAndCommit, rollback

from globals import TIMEOUT_CONFIRM_BOOKING, DEBUG

from celery_app.tasks import check_booking_status

def waiter_booking_status(booking_id, timeout):
    print(f'Checking booking status [{booking_id}]...')
    time.sleep(timeout)
    check_booking_status(booking_id)
    print(f'Booking status [{booking_id}] checked!')
    

def start_waiter_booking_status(booking_id, timeout=None):
    
    if DEBUG: #Only for testing
        load_dotenv()
        if os.getenv('EMAIL_TEST_MODE', 'False') == 'True':
            timeout = int(os.getenv('TIMEOUT_CONFIRM_BOOKING', TIMEOUT_CONFIRM_BOOKING))
            if timeout is None or timeout <= 0: return None
            print(f"TEST MODE - Waiting {timeout} seconds for booking status [{booking_id}]...")
            thread = threading.Thread(target=waiter_booking_status, args=(booking_id,timeout,)) # Mirar eficiencia
            thread.start()
            
            return timeout
            
    if timeout is None or timeout <= 0: return timeout
    
    timeout = int(timeout)
    
    check_booking_status.apply_async(args=[booking_id], countdown=60 * timeout)
    
    
    
    return timeout