
import os
import threading
import time

from dotenv import load_dotenv
from db import deleteAndCommit, rollback

from globals import PENDING_STATUS, TIMEOUT_CONFIRM_BOOKING
from helpers.BookingController import cancelBooking
from models.booking import BookingModel
from models.status import StatusModel

def check_booking_status(booking_id):
    
    booking = BookingModel.query.get(booking_id)
    
    if not booking: return

    if booking.status.status == PENDING_STATUS:
        cancelBooking(booking)

def waiter_booking_status(booking_id, timeout):
    print(f'Checking booking status [{booking_id}]...')
    # time.sleep(timeout*60)
    time.sleep(timeout)
    check_booking_status(booking_id)
    print('Booking status checked!')
    

def start_waiter_booking_status(booking_id, timeout=None):
    load_dotenv()
    if not timeout: timeout = TIMEOUT_CONFIRM_BOOKING
    if timeout is None or timeout <= 0: return timeout
    thread = threading.Thread(target=waiter_booking_status, args=(booking_id,timeout,)) # Mirar eficiencia
    thread.start()
    
    return timeout