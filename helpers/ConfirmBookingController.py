
import threading
import time
from db import deleteAndCommit, rollback

from globals import TIMEOUT_CONFIRM_BOOKING
from helpers.BookingController import cancelBooking
from models.booking import BookingModel

def check_booking_status(booking_id):
    
    booking = BookingModel.query.get(booking_id)
    
    if not booking: return
    
    cancelBooking(booking)
    
    try:
        # deleteAndCommit(booking)
        pass
    except Exception as e:
        rollback()
        raise e

def waiter_booking_status(booking_id, timeout):
    print(f'Checking booking status [{booking_id}]...')
    time.sleep(timeout*60)
    check_booking_status(booking_id)
    print('Booking status checked!')
    

def start_waiter_booking_status(booking_id, timeout=TIMEOUT_CONFIRM_BOOKING):
    
    thread = threading.Thread(target=waiter_booking_status, args=(booking_id,timeout,))
    thread.start()
    
    return timeout