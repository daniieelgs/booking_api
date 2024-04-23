
import os
import threading
import time

from dotenv import load_dotenv
from db import deleteAndCommit, rollback

from globals import TIMEOUT_CONFIRM_BOOKING, DEBUG, EmailType

from celery_app.tasks import check_booking_status, send_mail_task
from helpers.EmailController import send_cancelled_booking_mail, send_confirmed_booking_mail, send_updated_booking_mail
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
            if timeout is None or timeout <= 0: return None
            print(f"TEST MODE - Waiting {timeout} seconds for booking status [{booking_id}]...")
            thread = threading.Thread(target=waiter_booking_status, args=(booking_id,timeout,)) # Mirar eficiencia
            thread.start()
            
            return timeout
            
    if timeout is None or timeout <= 0: return timeout
    
    timeout = int(timeout)
    
    check_booking_status.apply_async(args=[booking_id], countdown=60 * timeout)
    
    
    
    return timeout

    
def send_confirmed_mail_async(local_id, booking_id, session_token_id):
    if DEBUG:
        load_dotenv()
        if os.getenv('EMAIL_TEST_MODE', 'False') == 'True': return send_email_debug(local_id, booking_id, session_token_id, EmailType.CONFIRMED_EMAIL)

    return send_mail_task.delay(local_id, booking_id, session_token_id, EmailType.CONFIRMED_EMAIL)   
    
def send_cancelled_mail_async(local_id, booking_id, session_token_id):
    if DEBUG:
        load_dotenv()
        if os.getenv('EMAIL_TEST_MODE', 'False') == 'True': return send_email_debug(local_id, booking_id, session_token_id, EmailType.CANCELLED_EMAIL)

    return send_mail_task.delay(local_id, booking_id, session_token_id, EmailType.CANCELLED_EMAIL)   

def send_updated_mail_async(local_id, booking_id, session_token_id):
    if DEBUG:
        load_dotenv()
        if os.getenv('EMAIL_TEST_MODE', 'False') == 'True': return send_email_debug(local_id, booking_id, session_token_id, EmailType.UPDATED_EMAIL)

    return send_mail_task.delay(local_id, booking_id, session_token_id, EmailType.UPDATED_EMAIL)

def send_email_debug(local_id, booking_id, booking_token_id, email_type: EmailType):
    
    local = LocalModel.query.get(local_id)
    booking = BookingModel.query.get(booking_id)
    token = SessionTokenModel.query.get(booking_token_id)
    
    
    
    if email_type == EmailType.CONFIRMED_EMAIL:
        send_mail = send_confirmed_booking_mail
    elif email_type == EmailType.CANCELLED_EMAIL:
        send_mail = send_cancelled_booking_mail
    elif email_type == EmailType.UPDATED_EMAIL:
        send_mail = send_updated_booking_mail
        
    send_mail(local, booking, token)