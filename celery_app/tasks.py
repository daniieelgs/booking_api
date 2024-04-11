import time
from celery import shared_task

@shared_task(queue='priority')
def notify_hello():
    print('Hello from notify_hello')
    
@shared_task(queue='default', ignore_result=False)
def check_booking(booking_id):
    print(f'Checking booking status for booking_id: {booking_id}')
    time.sleep(5)
    print(f'Booking status checked for booking_id: {booking_id}')
    
    return f"Booking '{booking_id}' OK!"