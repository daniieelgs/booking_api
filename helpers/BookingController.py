

from operator import or_
import random
from sqlite3 import OperationalError
import time

import redis
from db import addAndCommit, addAndFlush, beginSession, deleteAndCommit, new_session, rollback, db
from globals import CANCELLED_STATUS, CONFIRMED_STATUS, DONE_STATUS, MAX_TIMEOUT_WAIT_BOOKING, PENDING_STATUS, USER_ROLE, WEEK_DAYS, getApp
from helpers.Database import create_redis_connection, delete_key_value_cache, get_key_value_cache, register_key_value_cache
from helpers.DatetimeHelper import DATETIME_NOW, naiveToAware, now
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
from helpers.error.LocalError.LocalOverloadedException import LocalOverloadedException
from helpers.error.ModelNotFoundException import ModelNotFoundException
from helpers.error.SecurityError.InvalidTokenException import InvalidTokenException
from helpers.error.SecurityError.NoTokenProvidedException import NoTokenProvidedException
from helpers.error.SecurityError.TokenNotFound import TokenNotFoundException
from helpers.error.ServiceError.ServiceNotFoundException import ServiceNotFoundException
from helpers.error.StatusError.StatusNotFoundException import StatusNotFoundException
from helpers.error.WeekdayError.WeekdayNotFoundException import WeekdayNotFoundException
from helpers.error.WorkerError.WorkerNotFoundException import WorkerNotFoundException
from helpers.security import decodeToken, generateUUID
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

    local = LocalModel.query.get(local_id)
    
    if not local:
        raise LocalNotFoundException(id = local_id)
    
    if datetime_init == DATETIME_NOW:
        datetime_init = now(local.location)
    
    bookings_query = getBookingsQuery(local_id, datetime_init=datetime_init, datetime_end=datetime_end)

    status_ids = [StatusModel.query.filter(StatusModel.status == s).first().id for s in status] if status else None

    if status_ids:
        bookings_query = bookings_query.filter(BookingModel.status_id.in_(status_ids))
        
    if worker_id:
        bookings_query = bookings_query.filter(BookingModel.worker_id == worker_id)
        
    if service_id:
        bookings_query = bookings_query.filter(BookingModel.services.any(ServiceModel.id == service_id))
        
    if client_filter:
        if client_filter['name']: bookings_query = bookings_query.filter(or_(BookingModel.client_name.ilike(f'%{client_filter["name"]}%'), BookingModel.client_name.ilike(f'%{client_filter["name"].strip().title()}%')))
        if client_filter['email']: bookings_query = bookings_query.filter(BookingModel.client_email.ilike(f'%{client_filter["email"]}%'))
        if client_filter['tlf']: bookings_query = bookings_query.filter(BookingModel.client_tlf.ilike(f'%{client_filter["tlf"]}%'))
        
    if work_group_id:
        return [booking for booking in bookings_query.all() if booking.work_group_id == work_group_id]

    bookings = list(bookings_query.all())
    
    done_status = StatusModel.query.filter_by(status=DONE_STATUS).first()
    
    for booking in bookings:
        if naiveToAware(booking.datetime_end) < now(local.location) and booking.status != done_status:
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
    
    local = LocalModel.query.get(token.local_id)
    
    if not local:
        raise InvalidTokenException()
    
    if naiveToAware(exp_date) < now(local.location):
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

def waitBooking(local_id, date, MAX_TIMEOUT = MAX_TIMEOUT_WAIT_BOOKING, sleep_time = 0.2, uuid = None, pipeline = None):
    time_init = datetime.now()
    
    print(f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")}] [{uuid}] Waiting booking for local {local_id} on date {date}.')
    
    while True:
        
        time_end = datetime.now()
        
        if (time_end - time_init).seconds > MAX_TIMEOUT:
            print(f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")}] [{uuid}] Timeout waiting booking for local {local_id} on date {date}.')
            raise LocalOverloadedException(message='The local is overloaded. Try again later.')
        
        value = get_key_value_cache(local_id, pipeline=pipeline)
        print(f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")}] [{uuid}] get_key_value_cache: {value}')
        
        if not value:
            
            return value
        
        try:
            value = str(value.decode('utf-8'))
        except AttributeError:
            value = str(value)
        
        dates = value.split('|')
        
        print(f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")}] [{uuid}] Dates: {dates}')
        
        if str(date) in dates:
            print(f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")}] [{uuid}] Booking found for local {local_id} on date {date}. Waiting')
            time.sleep(sleep_time)
        else:
            print(f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")}] [{uuid}] Booking not found for local {local_id} on date {date}.')
            return value
    
    
def waitAndRegisterBooking(local_id, date, MAX_TIMEOUT=MAX_TIMEOUT_WAIT_BOOKING, uuid=None):
    uuid = generateUUID() if not uuid else uuid
    redis_connection = create_redis_connection()

    time_init = datetime.now()
    
    while (datetime.now() - time_init).seconds < MAX_TIMEOUT:

        with redis_connection.pipeline() as pipe:
            try:

                pipe.watch(local_id)

                value = waitBooking(local_id, date, MAX_TIMEOUT, uuid=uuid, redis_connection=redis_connection)

                if value:
                    new_value = value + f"|{str(date)}"
                else:
                    new_value = str(date)

                print(f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")}] [{uuid}] Registering booking for local {local_id} on date {date}. Value: {new_value}')

                pipe.multi()
                pipe.setex(local_id, MAX_TIMEOUT, new_value)
                pipe.execute()
                pipe.unwatch()
                return uuid
            finally:
                pipe.unwatch()

    raise LocalOverloadedException(message='The local is overloaded. Try again later.')
    
def unregisterBooking(local_id, date, uuid = None):
        
    print(f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")}]  [{uuid}] Unregistering booking for local {local_id} on date {date}.')
        
    value = get_key_value_cache(local_id)
    
    print(f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")}]  [{uuid}] get_key_value_cache: {value}')
    
    if not value:
        return value
    
    try:
        value = str(value.decode('utf-8'))
    except AttributeError:
        value = str(value)
    
    dates = value.split('|')
    
    if str(date) in dates:
        dates.remove(str(date))
        
        print(f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")}] [{uuid}] Dates: {dates}')
        
        if not dates:
            delete_key_value_cache(local_id)
        else:
        
            value = '|'.join(dates)
            
            print(f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")}] [{uuid}] Registering booking for local {local_id} on date {date}. Value: {value}')
            
            register_key_value_cache(local_id, value)
        
    return value

def createOrUpdateBooking(new_booking, local_id: int = None, bookingModel: BookingModel = None, commit = True, local:LocalModel = None, force = False):
    
    session = None    
            
    new_booking['services_ids'] = list(set(new_booking['services_ids']))
    new_booking['client_name'] = new_booking['client_name'].strip().title()
    
    if bookingModel:
        if [service.id for service in bookingModel.services] == new_booking['services_ids'] and 'worker_id' not in new_booking:
            new_booking['worker_id'] = bookingModel.worker_id
    
    if not local_id:
        if not local:
            raise LocalNotFoundException()
        local_id = local.id
    else:
        local = LocalModel.query.get(local_id)
        if not local:
            raise LocalNotFoundException(id = local_id)
    
    worker_id = new_booking['worker_id'] if 'worker_id' in new_booking else None
    
    try:
        datetime_init: datetime = naiveToAware(new_booking['datetime_init'])
    except ValueError:
        raise ValueError('Invalid date format.')
    
    if not force and datetime_init < now(local.location):
        raise PastDateException()
    
    total_duration = 0
    services = []
            
    date = datetime_init.date()
    
    uuid = None
    
    try:
        
        client_name = new_booking['client_name']
        
        uuid = waitAndRegisterBooking(local_id, date, uuid=client_name)
                    
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
        
        if not force and not getTimetable(local_id, week_day.id, datetime_init=datetime_init, datetime_end=datetime_end):
            raise LocalUnavailableException()
        
        if worker_id:
            worker = WorkerModel.query.get(worker_id)
            if not worker or worker.work_groups.first().local_id != local_id:
                raise WorkerNotFoundException(id = worker_id)
            
            if not force and services[0].work_group_id not in [wg.id for wg in worker.work_groups.all()]:
                raise WrongWorkerWorkGroupException()
            
            
            if not force:
                
                bookings = getBookings(local_id, datetime_init, datetime_end, status=[CONFIRMED_STATUS, PENDING_STATUS], worker_id=worker_id)
                    
                if bookings and (bookingModel is None or len(bookings) > 1 or bookings[0].id != bookingModel.id):
                    raise WorkerUnavailableException()
                
        else: 
                    
            workers = list(services[0].work_group.workers.all())
            
            worker_id = searchWorkerBookings(local_id, datetime_init, datetime_end, workers, bookingModel.id if bookingModel else None)
            
            if not worker_id:
                if not force:
                    raise AlredyBookingExceptionException()
                            
                workers = list(workers)
                
                random.shuffle(workers)
                
                worker_id = workers[0].id
        
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
                    do_commit = False
                    if status.status == CONFIRMED_STATUS:
                        confirmBooking(booking, session = session, commit=do_commit)
                    elif status.status == CANCELLED_STATUS:
                        cancelBooking(booking, session = session, commit=do_commit)
                    elif status.status == PENDING_STATUS:
                        pendingBooking(booking, session = session, commit=do_commit)
                
                for key, value in new_booking.items():
                    setattr(booking, key, value)
            
            max_attempts = 3
            
            for i in range(max_attempts):
            
                try:
                    addAndCommit(booking, session, rollback=False) if commit else addAndFlush(booking, session, rollback=False)
                except OperationalError as e:
                    if i == max_attempts - 1:
                        rollback(session)
                        raise e
                    time.sleep(1)
        except SQLAlchemyError as e:
            raise e
        
        if commit:
            unregisterBooking(local_id, date, uuid=uuid)
        
        def once(func):
            func.__called__ = False
            def wrapper(*args, **kwargs):
                if not func.__called__:
                    func.__called__ = True
                    return func(*args, **kwargs)
            return wrapper
        
        unregister_once_callback = once(lambda: unregisterBooking(local_id, date, uuid=uuid))
        
        return booking, unregister_once_callback
    
    except Exception as e:
        
        unregisterBooking(local_id, date, uuid=uuid)
        
        raise e

def calculatEndTimeBooking(booking):
    total_duration = sum(service.duration for service in booking.services)
    datetime_end = booking.datetime_init + timedelta(minutes=total_duration)
    booking.datetime_end = datetime_end
    return booking

def calculateExpireBookingToken(datetime_end: datetime, location):
                           
    datetime_end = datetime_end.replace(tzinfo=now().tzinfo)
                           
    diff = datetime_end - now(location)
                        
    return diff

def checkTimetableBookings(local_id):
    
    local = LocalModel.query.get(local_id)
    
    if not local:
        raise LocalNotFoundException(id = local_id)
    
    bookings = getBookings(local_id, datetime_init = DATETIME_NOW, datetime_end = None, status = [CONFIRMED_STATUS, PENDING_STATUS])
    
    for booking in bookings:
        week_day = WeekdayModel.query.filter_by(weekday=WEEK_DAYS[booking.datetime_init.weekday()]).first()
        if not getTimetable(local_id, week_day.id, datetime_init=booking.datetime_init, datetime_end=booking.datetime_end):
            raise BookingsConflictException(f'There is a booking [{booking.id}] that overlaps with the timetable.')
    
    return True

def cancelBooking(booking: BookingModel, comment = None, session = None, commit = True) -> BookingModel:
    return changeBookingStatus(booking, CANCELLED_STATUS, comment, session = session, commit = commit)
        
def confirmBooking(booking: BookingModel, comment = None, session = None, commit = True) -> BookingModel:
    return changeBookingStatus(booking, CONFIRMED_STATUS, comment, session = session, commit = commit)

def pendingBooking(booking: BookingModel, comment = None, session = None, commit = True) -> BookingModel:
    return changeBookingStatus(booking, PENDING_STATUS, comment, session = session, commit = commit)

def changeBookingStatus(booking, status_name, comment = None, session = None, commit = True) -> BookingModel:
    try:
        status = StatusModel.query.filter_by(status=status_name).first().id
        
        if not status:
            raise StatusNotFoundException(f"Status '{status_name}' was not found")
        
        booking.status_id = status
        if comment: booking.comment = comment
        addAndCommit(booking, session = session) if commit else addAndFlush(booking, session = session)
        return booking
    except SQLAlchemyError as e:
        rollback()
        raise e