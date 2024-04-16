import time
from celery import shared_task
from celery import current_task
from models.booking import BookingModel
from globals import PENDING_STATUS
from models.status import StatusModel
from helpers.BookingController import cancelBooking

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
        print(f'Booking {booking_id} cancelled!')
    else:
        print(f'Booking {booking_id} OK!')    
