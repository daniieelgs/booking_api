
import os
import threading
import time

from dotenv import load_dotenv
from db import deleteAndCommit, rollback

from globals import TIMEOUT_CONFIRM_BOOKING, DEBUG, USER_ROLE, EmailType, is_email_test_mode

from celery_app.tasks import check_booking_status, send_mail_task, set_email_sent
from helpers.BookingController import calculateExpireBookingToken
from helpers.EmailController import send_cancelled_booking_mail, send_confirmed_booking_mail, send_updated_booking_mail
from helpers.security import generateTokens
from models.booking import BookingModel
from models.local import LocalModel
from models.session_token import SessionTokenModel

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
            print("timeout:", timeout)
            if timeout is None or timeout <= 0: return None
            print(f"TEST MODE - Waiting {timeout} seconds for booking status [{booking_id}]...")
            thread = threading.Thread(target=waiter_booking_status, args=(booking_id,timeout,))
            thread.start()
            
            return timeout
            
    if timeout is None or timeout <= 0: return None
    
    timeout = int(timeout)
    
    check_booking_status.apply_async(args=[booking_id], countdown=60 * timeout)

    return timeout

    
def send_confirmed_mail_async(local_id, booking_id):
    if is_email_test_mode(): return send_mail_task(local_id, booking_id, EmailType.CONFIRMED_EMAIL)

    return send_mail_task.delay(local_id, booking_id, EmailType.CONFIRMED_EMAIL)   
    
def send_cancelled_mail_async(local_id, booking_id):
    if is_email_test_mode(): return send_mail_task(local_id, booking_id, EmailType.CANCELLED_EMAIL)

    return send_mail_task.delay(local_id, booking_id, EmailType.CANCELLED_EMAIL)   

def send_updated_mail_async(local_id, booking_id):
    if is_email_test_mode(): return send_mail_task(local_id, booking_id, EmailType.UPDATED_EMAIL)

    return send_mail_task.delay(local_id, booking_id, EmailType.UPDATED_EMAIL)


def send_email_debug(local_id, booking_id, email_type: EmailType):
    
    local = LocalModel.query.get(local_id)
    booking = BookingModel.query.get(booking_id)
    
    exp = calculateExpireBookingToken(booking.datetime_end, local.location)
    token = generateTokens(booking_id, local_id, refresh_token=True, expire_refresh=exp, user_role=USER_ROLE)
    
    if email_type == EmailType.CONFIRMED_EMAIL:
        send_mail = send_confirmed_booking_mail
    elif email_type == EmailType.CANCELLED_EMAIL:
        send_mail = send_cancelled_booking_mail
    elif email_type == EmailType.UPDATED_EMAIL:
        send_mail = send_updated_booking_mail
        
    success = send_mail(local, booking, token)
    
    set_email_sent(booking, email_type, success)