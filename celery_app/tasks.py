from datetime import datetime
import os
import time
from celery import shared_task
from celery import current_task
from dotenv import load_dotenv
import sqlalchemy
from db import addAndCommit, rollback
from helpers.Backup import backup_all
from helpers.EmailController import send_cancelled_booking_mail, send_confirmed_booking_mail, send_updated_booking_mail
from helpers.error.BookingError.BookingNotFoundException import BookingNotFoundException
from helpers.error.LocalError.LocalNotFoundException import LocalNotFoundException
from helpers.security import generateTokens, generateUUID
from models.booking import BookingModel
from globals import DEBUG, CANCELLED_STATUS, CONFIRMED_STATUS, FILENAME_LOG, PENDING_STATUS, EMAIL_CLAIM_TTL, MAX_RETRIES_SEND_EMAIL, RETRY_SEND_EMAIL, USER_ROLE, EmailType, is_email_test_mode, log
from models.local import LocalModel
from models.session_token import SessionTokenModel
from helpers.BookingController import calculateExpireBookingToken, cancelBooking
from helpers.Database import delete_key_value_cache, get_key_value_cache, register_key_value_cache, set_key_if_absent
     
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
        cancelBooking(booking) #TODO comment
        
        if is_email_test_mode(): return send_mail_task(booking.local_id, booking_id, int(EmailType.CANCELLED_EMAIL))
        
        send_mail_task.delay(booking.local_id, booking_id, int(EmailType.CANCELLED_EMAIL))   
    
def set_email_sent(booking, email_type: int, email_sent, commit = True):
    if email_type == int(EmailType.CONFIRMED_EMAIL): booking.email_confirmed = email_sent
    elif email_type == int(EmailType.CANCELLED_EMAIL): booking.email_cancelled = email_sent
    elif email_type == int(EmailType.UPDATED_EMAIL): booking.email_updated = email_sent
    else: raise Exception(f"Unknown email_type '{email_type}'.")
    
    if commit: addAndCommit(booking)
    
    return booking
        
# A task id is the same across retries and broker redeliveries of the same message, so it identifies "this" email
# request (a second update of a booking is a different task and still sends its own email). The key must outlive
# every possible retry plus an hour of margin.
EMAIL_SENT_KEY_TTL = 60 * RETRY_SEND_EMAIL * (MAX_RETRIES_SEND_EMAIL + 1) + 3600

def email_sent_key(task_id):
    return f'email_sent:{task_id}'

def email_already_sent(task_id):
    """True when a previous run of this same task already sent its email (e.g. Redis redelivered the message)."""
    if not task_id: return False
    try:
        return bool(get_key_value_cache(email_sent_key(task_id)))
    except Exception as e: # Redis down: better a possible duplicate than a lost email
        log("Could not check if the email was already sent.", level="WARNING", error=e)
        return False

# While a copy of the task is sending, another copy of the SAME task (Redis redelivered it, so both fire at the same
# ETA in different processes) must not send too. The claim is short on purpose: if the worker dies mid-send, the
# redelivery (>= visibility_timeout, 1 h by default) must find it expired and send the email (EMAIL_CLAIM_TTL).

def claim_email(task_id):
    """True if this copy may send now. Redis problems never block an email."""
    if not task_id: return True
    try:
        return set_key_if_absent(email_sent_key(task_id) + ':claim', 1, exp=EMAIL_CLAIM_TTL)
    except Exception as e:
        log("Could not claim the email.", level="WARNING", error=e)
        return True

def release_email_claim(task_id):
    if not task_id: return
    try:
        delete_key_value_cache(email_sent_key(task_id) + ':claim')
    except Exception as e:
        log("Could not release the email claim.", level="WARNING", error=e)

# One retry per attempt. A retry waiting longer than the broker's visibility_timeout is redelivered, so several copies
# of the SAME attempt (same task id and same retries counter) fire. Each copy that fails would schedule its own
# retry and the tasks would multiply on every cycle (measured: 11 sends in 560 s instead of 5). The first copy to
# finish an attempt records it; the others skip. Recorded when the attempt ENDS, so a worker that dies mid-attempt
# leaves it undone and the redelivered message runs it again.
def attempt_key(task_id, retries):
    return f'email_attempt_done:{task_id}:{retries}'

def attempt_already_done(task_id, retries):
    if not task_id: return False
    try:
        return bool(get_key_value_cache(attempt_key(task_id, retries)))
    except Exception as e:
        log("Could not check if the attempt was already done.", level="WARNING", error=e)
        return False

def mark_attempt_done(task_id, retries):
    if not task_id: return
    try:
        register_key_value_cache(attempt_key(task_id, retries), 1, exp=EMAIL_SENT_KEY_TTL)
    except Exception as e:
        log("Could not remember that the attempt was done.", level="WARNING", error=e)

def mark_email_sent(task_id):
    if not task_id: return
    try:
        register_key_value_cache(email_sent_key(task_id), 1, exp=EMAIL_SENT_KEY_TTL)
    except Exception as e:
        log("Could not remember that the email was sent.", level="WARNING", error=e)

@shared_task(bind=True, queue='priority', max_retries=MAX_RETRIES_SEND_EMAIL, default_retry_delay=60 * RETRY_SEND_EMAIL)
def send_mail_task(self, local_id, booking_id, email_type: int, _uuid = None):
     
    log(f"Sending email task. Email Type: {email_type}", uuid=_uuid)
    
    if email_already_sent(self.request.id):
        log(f"Email already sent by task {self.request.id}. Skipping the duplicate.", uuid=_uuid, level="WARNING")
        return
    
    if attempt_already_done(self.request.id, self.request.retries):
        log(f"Attempt {self.request.retries} of task {self.request.id} was already done by another copy. Skipping.", uuid=_uuid, level="WARNING")
        return
    
    if not claim_email(self.request.id):
        log(f"Another copy of task {self.request.id} is sending the email. Skipping.", uuid=_uuid, level="WARNING")
        return
    
    try:
        try:
            result = send_mail_task_body(self, local_id, booking_id, email_type, _uuid)
        except Exception: # includes the Retry that schedules the next attempt
            mark_attempt_done(self.request.id, self.request.retries)
            raise
        mark_attempt_done(self.request.id, self.request.retries)
        return result
    finally:
        release_email_claim(self.request.id) # after marking the attempt: a waiting copy sees one or the other

def send_mail_task_body(self, local_id, booking_id, email_type: int, _uuid = None):
     
    local = LocalModel.query.get(local_id)
    
    if not local:
        log("Local not found", uuid=_uuid, level="WARNING", save_cache=True)
        raise LocalNotFoundException(id=local_id)
    
    local_settings = local.local_settings
    if not local_settings:
        log("Local settings not found", uuid=_uuid, level="WARNING", save_cache=True)
        return
    
    # if not local_settings.booking_timeout or local_settings.booking_timeout == -1: return
    
    booking = BookingModel.query.get(booking_id)
    
    if not booking:
        log("Booking not found", uuid=_uuid, level="WARNING", save_cache=True)
        raise BookingNotFoundException(id = booking_id)
        
    exp = calculateExpireBookingToken(booking.datetime_end, local.location)
    
    token = generateTokens(booking_id, local_id, refresh_token=True, expire_refresh=exp, user_role=USER_ROLE)
                
    if email_type == int(EmailType.CONFIRMED_EMAIL):
        send_mail = send_confirmed_booking_mail
    elif email_type == int(EmailType.CANCELLED_EMAIL):
        send_mail = send_cancelled_booking_mail
    elif email_type == int(EmailType.UPDATED_EMAIL):
        send_mail = send_updated_booking_mail
    else:
        log(f"Unknown email_type '{email_type}'.", uuid=_uuid, level="WARNING", save_cache=True)
        raise Exception(f"Unknown email_type '{email_type}'. CONFIRMED_EMAIL '{EmailType.CONFIRMED_EMAIL}'. Check: {email_type == int(EmailType.CONFIRMED_EMAIL)}")
    
    try:
        success = send_mail(local, booking, token, _uuid = _uuid)
        log(f"Email sent: {success}", uuid=_uuid)
        if not success:
            
            set_email_sent(booking, email_type, False)
                        
            if is_email_test_mode(): return
                        
            raise Exception("Failed to send email booking")
        
        try:
            set_email_sent(booking, email_type, True)
        except Exception as e:
            log("FATAL ERROR. Error setting email sent", uuid=_uuid, error=e, level="ERROR", save_cache=True)
            rollback()
            raise e
        
        mark_email_sent(self.request.id)
        
    except Exception as exc:
        #self.default_retry_delay
        log(f"Error sending email. Retrying in {self.default_retry_delay} seconds.", uuid=_uuid, error=exc, level="ERROR", save_cache=True)
        self.retry(exc=exc)
        
#execue at especific time
@shared_task(queue='default')
def daily_worker():
    uuid = generateUUID()
    log('Daily worker executed at:', time.strftime('%X'), uuid=uuid)
    
    backup_all(_uuid_log=uuid)
    
    log('Daily worker finished at:', time.strftime('%X'), uuid=uuid, save_cache=True)
    
    #TODO: Add more tasks. Crear vistas en la base datos y eliminar reservas antiguas. Optimizar la base de datos.
