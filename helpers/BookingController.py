

from operator import or_
import random
import traceback
from db import addAndCommit, addAndFlush, deleteAndCommit, rollback
from globals import CANCELLED_STATUS, CONFIRMED_STATUS, DONE_STATUS, PENDING_STATUS, USER_ROLE, WEEK_DAYS
from helpers.TimetableController import getTimetable
from sqlalchemy import and_
from sqlalchemy.exc import SQLAlchemyError
from helpers.error.BookingError.AlredyBookingException import AlredyBookingExceptionException
from helpers.error.BookingError.BookingNotFoundError import BookingNotFoundException
from helpers.error.BookingError.BookingsConflictException import BookingsConflictException
from helpers.error.BookingError.LocalUnavailableException import LocalUnavailableException
from helpers.error.DataError.PastDateException import PastDateException
from helpers.error.BookingError.WorkerUnavailable import WorkerUnavailableException
from helpers.error.BookingError.WrongServiceWorkGroupException import WrongServiceWorkGroupException
from helpers.error.BookingError.WrongWorkerWorkGroupException import WrongWorkerWorkGroupException
from helpers.error.LocalError.LocalNotFoundException import LocalNotFoundException
from helpers.error.ModelNotFoundException import ModelNotFoundException
from helpers.error.SecurityError.InvalidTokenException import InvalidTokenException
from helpers.error.SecurityError.NoTokenProvidedException import NoTokenProvidedException
from helpers.error.SecurityError.TokenNotFound import TokenNotFoundException
from helpers.error.ServiceError.ServiceNotFoundException import ServiceNotFoundException
from helpers.error.StatusError.StatusNotFoundException import StatusNotFoundException
from helpers.error.WeekdayError.WeekdayNotFoundException import WeekdayNotFoundException
from helpers.error.WorkerError.WorkerNotFoundException import WorkerNotFoundException
from helpers.security import decodeToken
from models.booking import BookingModel
from models.local import LocalModel
from models.service import ServiceModel
from models.session_token import SessionTokenModel
from models.status import StatusModel
from models.weekday import WeekdayModel
from models.work_group import WorkGroupModel

from datetime import datetime, timedelta

from models.worker import WorkerModel

def getBookingsQuery(local_id, datetime_init = None, datetime_end = None):
    work_group = WorkGroupModel.query.filter_by(local_id=local_id).all()
    workers = [wg.workers.all() for wg in work_group]
    worker_ids = set([worker.id for worker_list in workers for worker in worker_list])
    
    query = BookingModel.query.filter(BookingModel.worker_id.in_(worker_ids))
    
    if datetime_init and datetime_end:
        query = query.filter(and_(BookingModel.datetime_end > datetime_init, 
                                  BookingModel.datetime_init < datetime_end))
    elif datetime_init:
        query = query.filter(BookingModel.datetime_end > datetime_init)
    
    return query

def getBookings(local_id, datetime_init, datetime_end, status = None, worker_id = None, service_id = None, work_group_id = None, client_filter = None):

    bookings_query = getBookingsQuery(local_id, datetime_init=datetime_init, datetime_end=datetime_end)

    status_ids = [StatusModel.query.filter(StatusModel.status == s).first().id for s in status] if status else None

    if status_ids:
        bookings_query = bookings_query.filter(BookingModel.status_id.in_(status_ids))
        
    if worker_id:
        bookings_query = bookings_query.filter(BookingModel.worker_id == worker_id)
        
    if service_id:
        bookings_query = bookings_query.filter(BookingModel.services.any(ServiceModel.id == service_id))
        
    if client_filter:
        if client_filter['name']: bookings_query = bookings_query.filter(BookingModel.client_name.ilike(f'%{client_filter["name"]}%'))
        if client_filter['email']: bookings_query = bookings_query.filter(BookingModel.client_email.ilike(f'%{client_filter["email"]}%'))
        if client_filter['tlf']: bookings_query = bookings_query.filter(BookingModel.client_tlf.ilike(f'%{client_filter["tlf"]}%'))
        
    if work_group_id:
        return [booking for booking in bookings_query.all() if booking.work_group_id == work_group_id]

    bookings = list(bookings_query.all())
    
    done_status = StatusModel.query.filter_by(status=DONE_STATUS).first()
    
    for booking in bookings:
        if booking.datetime_end < datetime.now() and booking.status != done_status:
            booking.status = done_status
            try:
                addAndCommit(booking)
            except SQLAlchemyError as e:
                rollback()
                raise e
            
            if status_ids and done_status.id not in status_ids:
                bookings.remove(booking)
    
    return bookings

def getBookingBySession(token):
    
    if not token:
        raise NoTokenProvidedException()
    
    decoded = decodeToken(token)
        
    token_id = decoded['token']
    booking_id = decoded['sub']
    exp = decoded['exp'] if 'exp' in decoded else 0
    exp_date = datetime.fromtimestamp(exp)
    
    token = SessionTokenModel.query.get(token_id)
    
    if not token:
        raise TokenNotFoundException('Session token not found.')
    
    if token.jti != decoded['jti'] or token.user_session.user != USER_ROLE:
        raise InvalidTokenException()
    
    if exp_date < datetime.now():
        try:
            deleteAndCommit(token)
        except SQLAlchemyError as e:
            rollback()
            raise e  
        
        raise InvalidTokenException('The session token has expired.')    
    
    booking = BookingModel.query.get(booking_id)
    
    if not booking:
        raise BookingNotFoundException(id=booking_id)
    
    if booking.local_id != token.local_id:
        raise InvalidTokenException()
    
    return booking

def searchWorkerBookings(local_id, datetime_init, datetime_end, workers, booking_id):
    workers = list(workers)
    
    random.shuffle(workers)
    
    for worker in workers:
        bookings = getBookings(local_id, datetime_init, datetime_end, status=[CONFIRMED_STATUS, PENDING_STATUS], worker_id=worker.id)
        if bookings and (booking_id is None or len(bookings) > 1 or bookings[0].id != booking_id):
            continue
        
        return worker.id
    
    return None

def deserializeBooking(booking):
    return {
        'worker_id': booking.worker_id,
        'services_ids': [service.id for service in booking.services],
        'datetime_init': booking.datetime_init,
        'status_id': booking.status_id,
        'client_name': booking.client_name,
        'client_tlf': booking.client_tlf,
        'comment': booking.comment,
        'client_email': booking.client_email,
        'status': booking.status.status
    }

def createOrUpdateBooking(new_booking, local_id, bookingModel: BookingModel = None, commit = True):
    
    new_booking['services_ids'] = list(set(new_booking['services_ids']))
    new_booking['client_name'] = new_booking['client_name'].strip().title()
    
    if bookingModel:
        if [service.id for service in bookingModel.services] == new_booking['services_ids'] and 'worker_id' not in new_booking:
            new_booking['worker_id'] = bookingModel.worker_id
    
    local = LocalModel.query.get(local_id)
    if not local:
        raise LocalNotFoundException(id = local_id)
    
    worker_id = new_booking['worker_id'] if 'worker_id' in new_booking else None
    
    try:
        datetime_init = new_booking['datetime_init']
    except ValueError:
        raise ValueError('Invalid date format.')
    
    if datetime_init < datetime.now():
        raise PastDateException()
    
    total_duration = 0
    services = []
            
    for service_id in new_booking['services_ids']:
        service = ServiceModel.query.get(service_id)
        if not service or service.work_group.local_id != local_id:
            raise ServiceNotFoundException(id = service_id)
        total_duration += service.duration
        
        if len(services) > 0 and service.work_group_id != services[0].work_group_id:
            raise WrongServiceWorkGroupException()
            
        services.append(service)
        
    if not services:
        raise ServiceNotFoundException(id = 0)
    
    new_booking.pop('services_ids')
    
    datetime_end = datetime_init + timedelta(minutes=total_duration)
        
    new_booking['datetime_end'] = datetime_end
            
    week_day = WeekdayModel.query.filter_by(weekday=WEEK_DAYS[datetime_init.weekday()]).first()
    
    if not week_day:
        raise WeekdayNotFoundException()
    
    if not getTimetable(local_id, week_day.id, datetime_init=datetime_init, datetime_end=datetime_end):
        raise LocalUnavailableException()
    
    if worker_id:
        worker = WorkerModel.query.get(worker_id)
        if not worker or worker.work_groups.first().local_id != local_id:
            raise WorkerNotFoundException(id = worker_id)
        
        if services[0].work_group_id not in [wg.id for wg in worker.work_groups.all()]:
            raise WrongWorkerWorkGroupException()
            
        bookings = getBookings(local_id, datetime_init, datetime_end, status=[CONFIRMED_STATUS, PENDING_STATUS], worker_id=worker_id)
            
        if bookings and (bookingModel is None or len(bookings) > 1 or bookings[0].id != bookingModel.id):
            raise WorkerUnavailableException()
             
    else: 
                
        workers = list(services[0].work_group.workers.all())
        
        worker_id = searchWorkerBookings(local_id, datetime_init, datetime_end, workers, bookingModel.id if bookingModel else None)
        
        if not worker_id:
            raise AlredyBookingExceptionException()
    
    new_status = new_booking.pop('status') if 'status' in new_booking else (PENDING_STATUS if bookingModel is None else bookingModel.status.status)
    
    status = StatusModel.query.filter_by(status=new_status).first()
    
    if not status:
        raise StatusNotFoundException()
    
    new_booking['status_id'] = status.id
    new_booking['worker_id'] = worker_id
    
    booking = bookingModel or BookingModel(**new_booking)
    booking.services = services
    
    try:
        
        if bookingModel:
        
            if bookingModel.status_id != status.id:
                if status.status == CONFIRMED_STATUS:
                    confirmBooking(booking)
                elif status.status == CANCELLED_STATUS:
                    cancelBooking(booking)
                elif status.status == PENDING_STATUS:
                    pendingBooking(booking)
            
            for key, value in new_booking.items():
                setattr(booking, key, value)
        
        addAndCommit(booking) if commit else addAndFlush(booking)
    except SQLAlchemyError as e:
        rollback()
        raise e
    return booking

def calculatEndTimeBooking(booking):
    total_duration = sum(service.duration for service in booking.services)
    datetime_end = booking.datetime_init + timedelta(minutes=total_duration)
    booking.datetime_end = datetime_end
    return booking

def checkTimetableBookings(local_id):
    
    bookings = getBookings(local_id, datetime_init = datetime.now(), datetime_end = None, status = [CONFIRMED_STATUS, PENDING_STATUS])
    
    for booking in bookings:
        week_day = WeekdayModel.query.filter_by(weekday=WEEK_DAYS[booking.datetime_init.weekday()]).first()
        if not getTimetable(local_id, week_day.id, datetime_init=booking.datetime_init, datetime_end=booking.datetime_end):
            raise BookingsConflictException(f'There is a booking [{booking.id}] that overlaps with the timetable.')
    
    return True

def cancelBooking(booking: BookingModel, comment = None):
    changeBookingStatus(booking, CANCELLED_STATUS)
    

def confirmBooking(booking: BookingModel, comment = None):
    changeBookingStatus(booking, CONFIRMED_STATUS)

def pendingBooking(booking: BookingModel, comment = None):
    changeBookingStatus(booking, PENDING_STATUS)

def changeBookingStatus(booking, status):
    try:
        booking.status_id = StatusModel.query.filter_by(status=status).first().id
        addAndCommit(booking)
    except SQLAlchemyError as e:
        rollback()
        raise e