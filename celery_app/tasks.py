import time
from celery import shared_task
from celery import current_task
from helpers.EmailController import send_cancelled_booking_mail, send_confirmed_booking_mail, send_updated_booking_mail
from helpers.error.BookingError.BookingNotFoundException import BookingNotFoundException
from helpers.error.LocalError.LocalNotFoundException import LocalNotFoundException
from helpers.security import generateTokens
from models.booking import BookingModel
from globals import CANCELLED_STATUS, CONFIRMED_STATUS, PENDING_STATUS, RETRY_SEND_EMAIL, USER_ROLE, EmailType
from models.local import LocalModel
from models.session_token import SessionTokenModel
from helpers.BookingController import calculateExpireBookingToken, cancelBooking

@shared_task(queue='priority')
def notify_hello():
    # print('Hello from notify_hello')
    pass
    
@shared_task(queue='default', ignore_result=False)
def check_booking(booking_id):
    print(f'Checking booking status for booking_id: {booking_id}')
    time.sleep(5)
    print(f'Booking status checked for booking_id: {booking_id}')
    
    return f"Booking '{booking_id}' OK!"

def your_email_sending_function(email_info):
    # Lógica para enviar el email
    return False

@shared_task(bind=True, queue='priority', max_retries=3, default_retry_delay=5)  # X es el número de horas entre intentos
def send_email(self, email_info):
    try:
        # Lógica para enviar el email
        print(f'Enviando correo electrónico a {email_info}...')
        success = your_email_sending_function(email_info)
        if not success:
            raise Exception("El envío de correo electrónico falló.")
    except Exception as exc:
        # Esto reintentará la tarea
        print(f'Error al enviar el correo, intentando de nuevo en {self.default_retry_delay} segundos...')
        self.retry(exc=exc)        
        
        
        
        
@shared_task(queue='default')   
def check_booking_status(booking_id):
    
    print(f'Checking booking status for booking_id: {booking_id}')
    
    booking = BookingModel.query.get(booking_id)
    
    if not booking: 
        print(f'Booking {booking_id} not found!')
        return

    if booking.status.status == PENDING_STATUS:
        cancelBooking(booking)
        
@shared_task(bind=True, queue='priority', max_retries=3, default_retry_delay=60 * RETRY_SEND_EMAIL)
def send_mail_task(self, local_id, booking_id, email_type: EmailType):
     
    local = LocalModel.query.get(local_id)
    
    if not local:
        raise LocalNotFoundException(id=local_id)
    
    local_settings = local.local_settings
    if not local_settings: return
    
    if not local_settings.booking_timeout or local_settings.booking_timeout == -1: return
    
    booking = BookingModel.query.get(booking_id)
    
    if not booking:
        raise BookingNotFoundException(id = booking_id)
        
    exp = calculateExpireBookingToken(booking.datetime_end, local.location)
    
    token = generateTokens(booking_id, local_id, refresh_token=True, expire_refresh=exp, user_role=USER_ROLE)
        
    if email_type == EmailType.CONFIRMED_EMAIL:
        send_mail = send_confirmed_booking_mail
    elif email_type == EmailType.CANCELLED_EMAIL:
        send_mail = send_cancelled_booking_mail
    elif email_type == EmailType.UPDATED_EMAIL:
        send_mail = send_updated_booking_mail
    else:
        raise Exception(f"Unknown email_type '{email_type}'.")
    
    try:
        success = send_mail(local, booking, token)
        if not success:
            raise Exception("Failed to send confirmed booking to")
    except Exception as exc:
        #self.default_retry_delay
        self.retry(exc=exc)