

import random
import traceback
from db import addAndCommit, addAndFlush, deleteAndCommit, rollback
from globals import CONFIRMED_STATUS, PENDING_STATUS, USER_ROLE, WEEK_DAYS
from helpers.TimetableController import getTimetable
from sqlalchemy import and_
from sqlalchemy.exc import SQLAlchemyError
from helpers.error.BookingError.AlredyBookingException import AlredyBookingExceptionException
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

def getBookings(local_id, datetime_init, datetime_end, status = None, worker_id = None, work_group_id = None):

    bookings_query = getBookingsQuery(local_id, datetime_init=datetime_init, datetime_end=datetime_end)

    status_ids = [StatusModel.query.filter(StatusModel.status == s).first().id for s in status] if status else None

    if status_ids:
        bookings_query = bookings_query.filter(BookingModel.status_id.in_(status_ids))
        
    if worker_id:
        bookings_query = bookings_query.filter(BookingModel.worker_id == worker_id)
        
    if work_group_id:
        bookings_query = bookings_query.filter(BookingModel.work_group_id == work_group_id)

    return bookings_query.all()

def getBookingBySession(token):
    
    if not token:
        raise NoTokenProvidedException()
    
    decoded = decodeToken(token)
        
    token_id = decoded['token']
    booking_id = decoded['sub']
    exp = decoded['exp']
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
    
    booking = BookingModel.query.get_or_404(booking_id)
    
    if booking.local_id != token.local_id:
        raise InvalidTokenException()
    
    return booking

def createOrUpdateBooking(new_booking, local_id, bookingModel: BookingModel = None, commit = True):
    
    local = LocalModel.query.get(local_id)
    if not local:
        raise LocalNotFoundException(id = local_id)
    
    worker_id = new_booking['worker_id'] if 'worker_id' in new_booking else None
    
    try:
        datetime_init = new_booking['datetime']
    except ValueError:
        raise ValueError('Invalid date format.')
    
    if datetime_init < datetime.now():
        raise PastDateException()
    
    total_duration = 0
    services = []
            
    for service_id in set(new_booking['services_ids']):
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
            
        if bookings and (len(bookings) > 1 or bookings[0].id != bookingModel.id):
            raise WorkerUnavailableException()
             
    else: 
        workers = list(services[0].work_group.workers.all())
        
        random.shuffle(workers)
        
        for worker in workers:
            bookings = getBookings(local_id, datetime_init, datetime_end, status=[CONFIRMED_STATUS, PENDING_STATUS], worker_id=worker.id)
            if bookings and (len(bookings) > 1 or bookings[0].id != bookingModel.id):
                continue
            
            worker_id = worker.id
            break
        
        if not worker_id:
            raise AlredyBookingExceptionException()
    
    new_status = new_booking.pop('status_id') if 'status_id' in new_booking else PENDING_STATUS
    
    status = StatusModel.query.filter_by(status=new_status).first()
    
    if not status:
        raise StatusNotFoundException()
    
    new_booking['status_id'] = status.id
    new_booking['worker_id'] = worker_id
    
    booking = bookingModel or BookingModel(**new_booking)
    booking.services = services
    
    booking = calculatEndTimeBooking(booking) #TODO : al actualizar el tiempo de un service actualizar el tiempo de todos sus bookings
    
    if bookingModel:
        for key, value in new_booking.items():
            setattr(booking, key, value)
    
    try:
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