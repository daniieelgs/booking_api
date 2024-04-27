from logging import DEBUG
import os
import time
from celery import shared_task
from celery import current_task
from dotenv import load_dotenv
import sqlalchemy
from db import addAndCommit, rollback
from helpers.EmailController import send_cancelled_booking_mail, send_confirmed_booking_mail, send_updated_booking_mail
from helpers.error.BookingError.BookingNotFoundException import BookingNotFoundException
from helpers.error.LocalError.LocalNotFoundException import LocalNotFoundException
from helpers.security import generateTokens
from models.booking import BookingModel
from globals import CANCELLED_STATUS, CONFIRMED_STATUS, PENDING_STATUS, RETRY_SEND_EMAIL, USER_ROLE, EmailType, is_email_test_mode
from models.local import LocalModel
from models.session_token import SessionTokenModel
from helpers.BookingController import calculateExpireBookingToken, cancelBooking
     
@shared_task(queue='default')   
def check_booking_status(booking_id):
    
    print(f'Checking booking status for booking_id: {booking_id}')
    
    try:
        booking = BookingModel.query.get(booking_id)
    except sqlalchemy.exc.OperationalError as e:
        if DEBUG: #Only for testing
            if os.getenv('EMAIL_TEST_MODE', 'False') == 'True':
                short_msg_error = str(e).split('\n')[0]
                print(f'TEST MODE OperationalError: {short_msg_error}')
                return
                        
        raise e
    
    if not booking: 
        print(f'Booking {booking_id} not found!')
        return

    if booking.status.status == PENDING_STATUS:
        cancelBooking(booking)
        
        if is_email_test_mode(): return send_mail_task(booking.local_id, booking_id, int(EmailType.CANCELLED_EMAIL))
        
        send_mail_task.delay(booking.local_id, booking_id, int(EmailType.CANCELLED_EMAIL))   
    
def set_email_sent(booking, email_type: int, email_sent, commit = True):
    if email_type == int(EmailType.CONFIRMED_EMAIL): booking.email_confirmed = email_sent
    elif email_type == int(EmailType.CANCELLED_EMAIL): booking.email_cancelled = email_sent
    elif email_type == int(EmailType.UPDATED_EMAIL): booking.email_updated = email_sent
    else: raise Exception(f"Unknown email_type '{email_type}'.")
    
    if commit: addAndCommit(booking)
    
    return booking
        
@shared_task(bind=True, queue='priority', max_retries=3, default_retry_delay=60 * RETRY_SEND_EMAIL)
def send_mail_task(self, local_id, booking_id, email_type: int):
     
    local = LocalModel.query.get(local_id)
    
    if not local:
        raise LocalNotFoundException(id=local_id)
    
    local_settings = local.local_settings
    if not local_settings: return
    
    # if not local_settings.booking_timeout or local_settings.booking_timeout == -1: return
    
    booking = BookingModel.query.get(booking_id)
    
    if not booking:
        raise BookingNotFoundException(id = booking_id)
        
    exp = calculateExpireBookingToken(booking.datetime_end, local.location)
    
    token = generateTokens(booking_id, local_id, refresh_token=True, expire_refresh=exp, user_role=USER_ROLE)
        
    print("Email type:", email_type)
    print("CONFIRMED_EMAIL:", EmailType.CONFIRMED_EMAIL)
    print("Check:", email_type == int(EmailType.CONFIRMED_EMAIL))
        
    if email_type == int(EmailType.CONFIRMED_EMAIL):
        send_mail = send_confirmed_booking_mail
    elif email_type == int(EmailType.CANCELLED_EMAIL):
        send_mail = send_cancelled_booking_mail
    elif email_type == int(EmailType.UPDATED_EMAIL):
        send_mail = send_updated_booking_mail
    else:
        raise Exception(f"Unknown email_type '{email_type}'. CONFIRMED_EMAIL '{EmailType.CONFIRMED_EMAIL}'. Check: {email_type == int(EmailType.CONFIRMED_EMAIL)}")
    
    try:
        success = send_mail(local, booking, token)
        if not success:
            
            set_email_sent(booking, email_type, False)
                        
            if is_email_test_mode(): return
                        
            raise Exception("Failed to send email booking")
        
        try:
            set_email_sent(booking, email_type, True)
        except Exception as e:
            rollback()
            raise e
        
    except Exception as exc:
        #self.default_retry_delay
        self.retry(exc=exc)