from datetime import datetime, timedelta
import random
from flask import request
from flask.views import MethodView
from flask_smorest import Blueprint, abort
from helpers.BookingController import createOrUpdateBooking, getBookings, getBookingBySession as getBookingBySessionHelper
from helpers.ConfirmBookingController import start_waiter_booking_status
from helpers.DataController import getDataRequest, getWeekDataRequest
from helpers.TimetableController import getTimetable
from helpers.error.BookingError.AlredyBookingException import AlredyBookingExceptionException
from helpers.error.BookingError.LocalUnavailableException import LocalUnavailableException
from helpers.error.DataError.PastDateException import PastDateException
from helpers.error.BookingError.WorkerUnavailable import WorkerUnavailableException
from helpers.error.BookingError.WrongServiceWorkGroupException import WrongServiceWorkGroupException
from helpers.error.BookingError.WrongWorkerWorkGroupException import WrongWorkerWorkGroupException
from helpers.error.DataError.UnspecifedDateException import UnspecifedDateException
from helpers.error.ModelNotFoundException import ModelNotFoundException
from helpers.error.SecurityError.InvalidTokenException import InvalidTokenException
from helpers.error.SecurityError.NoTokenProvidedException import NoTokenProvidedException
from helpers.error.SecurityError.TokenNotFound import TokenNotFoundException
from helpers.error.StatusError.StatusNotFoundException import StatusNotFoundException
from helpers.error.WeekdayError.WeekdayNotFoundException import WeekdayNotFoundException
from helpers.security import decodeToken, generateTokens
from models.booking import BookingModel
from models.local import LocalModel
from db import addAndFlush, addAndCommit, commit, deleteAndFlush, deleteAndCommit, flush, rollback
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy.exc import SQLAlchemyError, OperationalError
import traceback

from globals import DEBUG, CONFIRMED_STATUS, PENDING_STATUS, SESSION_GET, STATUS_LIST_GET, USER_ROLE, WEEK_DAYS, WORK_GROUP_ID_GET, WORKER_ID_GET
from models.service import ServiceModel
from models.session_token import SessionTokenModel
from models.status import StatusModel
from models.weekday import WeekdayModel
from models.worker import WorkerModel
from schema import BookingAdminParams, BookingAdminSchema, BookingAdminWeekParams, BookingParams, BookingSchema, BookingSessionParams, BookingWeekParams, NewBookingSchema, PublicBookingSchema, StatusSchema

blp = Blueprint('booking', __name__, description='Booking CRUD')

def getBookingBySession(token):
    try:
        return getBookingBySessionHelper(token)
    except NoTokenProvidedException as e:
        abort(400, message=str(e))
    except InvalidTokenException as e:
        abort(401, message=str(e))
    except TokenNotFoundException as e:
        abort(404, message=str(e))
    except Exception as e:
        traceback.print_exc()
        abort(500, message=str(e) if DEBUG else 'Could not get the booking.')

@blp.route('/local/<string:local_id>')
class SeePublicBooking(MethodView):
    
    @blp.arguments(BookingParams, location='query')
    @blp.response(404, description='The local was not found')
    @blp.response(422, description='Unspecified date.')
    @blp.response(204, description='The local does not have bookings.')
    @blp.response(200, PublicBookingSchema(many=True))
    def get(self, local_id):
        """
        Retrieves public bookings from specific DateTime.
        """      
        
        try:
            datetime_init, datetime_end = getDataRequest(request)
        except ValueError as e:
            abort(400, message=str(e))
        except UnspecifedDateException as e:
            abort(422, message=str(e))    
        
        worker_id = request.args.get(WORKER_ID_GET, None)
        work_group_id = request.args.get(WORK_GROUP_ID_GET, None)
        
        bookings = getBookings(local_id, datetime_init, datetime_end, status=[CONFIRMED_STATUS, PENDING_STATUS], worker_id=worker_id, work_group_id=work_group_id)
                
        return bookings
    
@blp.route('/local/<string:local_id>/week')
class SeePublicBookingWeek(MethodView):
    
    @blp.arguments(BookingWeekParams, location='query')
    @blp.response(404, description='The local was not found')
    @blp.response(422, description='Unspecified date.')
    @blp.response(204, description='The local does not have bookings.')
    @blp.response(200, PublicBookingSchema(many=True))
    def get(self, local_id):
        """
        Retrieves public bookings from a week
        """
        
        try:
            datetime_init, datetime_end = getWeekDataRequest(request)
        except ValueError as e:
            abort(400, message=str(e))
        except UnspecifedDateException as e:
            abort(422, message=str(e))    
            
        worker_id = request.args.get(WORKER_ID_GET, None)
        work_group_id = request.args.get('work_group_id', None)
                        
        return getBookings(local_id, datetime_init, datetime_end, status=[CONFIRMED_STATUS, PENDING_STATUS], worker_id=worker_id, work_group_id=work_group_id)
    
@blp.route('/all')
class SeePublicBookingWeek(MethodView):
    
    @blp.arguments(BookingAdminParams, location='query')
    @blp.response(404, description='The local was not found')
    @blp.response(422, description='Unspecified date.')
    @blp.response(204, description='The local does not have bookings.')
    @blp.response(200, BookingSchema(many=True))
    @jwt_required(refresh=True)
    def get(self):
        """
        Retrieves private data bookings from specific DateTime.
        """      
        
        try:
            datetime_init, datetime_end = getDataRequest(request)
        except ValueError as e:
            abort(400, message=str(e))
        except UnspecifedDateException as e:
            abort(422, message=str(e))    
        
        worker_id = request.args.get(WORKER_ID_GET, None)
        work_group_id = request.args.get(WORK_GROUP_ID_GET, None)
        status = request.args.get(STATUS_LIST_GET, None)
        if status:
            status = status.split(',')
        
        bookings = getBookings(get_jwt_identity(), datetime_init, datetime_end, status=status, worker_id=worker_id, work_group_id=work_group_id)
                
        return bookings
    
@blp.route('/all/week')
class SeePublicBookingWeek(MethodView):
    
    @blp.arguments(BookingAdminWeekParams, location='query')
    @blp.response(404, description='The local was not found')
    @blp.response(422, description='Unspecified date.')
    @blp.response(204, description='The local does not have bookings.')
    @blp.response(200, BookingSchema(many=True))
    @jwt_required(refresh=True)
    def get(self):
        """
        Retrieves private data bookings from a week
        """
        
        try:
            datetime_init, datetime_end = getWeekDataRequest(request)
        except ValueError as e:
            abort(400, message=str(e))
        except UnspecifedDateException as e:
            abort(422, message=str(e))    
            
        worker_id = request.args.get(WORKER_ID_GET, None)
        work_group_id = request.args.get(WORK_GROUP_ID_GET, None)
        status = request.args.get(STATUS_LIST_GET, None)
        if status:
            status = status.split(',')
                        
        return getBookings(get_jwt_identity(), datetime_init, datetime_end, status=status, worker_id=worker_id, work_group_id=work_group_id)
    
@blp.route('/local/<string:local_id>')
class Booking(MethodView):
    
    # TODO : definir comportamiento al eliminar un servicio, trabajador o work group y al actualizar el timetable
    # TODO : definir comportamiento al cambiar un trabajador de work group o un servicio de work group
    @blp.arguments(BookingSchema)
    @blp.response(404, description='The local was not found. The service was not found. The worker was not found.')
    @blp.response(400, description='Invalid date format. No session token provided.')
    @blp.response(401, description='The session token is invalid.')
    @blp.response(409, description='There is already a booking in that time. The worker is not available. The services must be from the same work group. The worker must be from the same work group that the services. The local is not available. The date is in the past.')
    @blp.response(201, NewBookingSchema)
    def post(self, new_booking, local_id):
        """
        Creates a new booking.
        """
        try:
            booking = createOrUpdateBooking(new_booking, local_id, commit=False)
            
            datetime_end = booking.datetime_end
            
            timeout = start_waiter_booking_status(booking.id, 0.083)
                
            diff = datetime_end - datetime.now()
            
            exp = timedelta(days=diff.days, hours=diff.seconds//3600, minutes=(diff.seconds % 3600) // 60)
            
            token = generateTokens(booking.id, booking.local_id, refresh_token=True, expire_refresh=exp, user_role=USER_ROLE)
            
            commit()
            
            return {
                "booking": booking,
                "timeout": timeout,
                "session_token": token
            }
        except (StatusNotFoundException, WeekdayNotFoundException) as e:
            abort(500, message = str(e))
        except ModelNotFoundException as e:
            abort(404, message = str(e))
        except ValueError as e:
            abort(400, message = str(e))
        except (PastDateException, WrongServiceWorkGroupException, LocalUnavailableException, WrongWorkerWorkGroupException, WorkerUnavailableException, AlredyBookingExceptionException) as e:
            abort(409, message = str(e))
        except Exception as e:
            traceback.print_exc()
            rollback()
            abort(500, message = str(e) if DEBUG else 'Could not create the booking.')   
             

@blp.route('/<int:booking_id>')
class BookingAdmin(MethodView):
    
    @blp.response(404, description='The booking was not found.')
    @blp.response(401, description='You are not allowed to get the booking.')
    @blp.response(200, BookingSchema)
    @jwt_required(refresh=True)
    def get(self, booking_id):
        """
        Retrieves a booking.
        """
        
        booking = BookingModel.query.get_or_404(booking_id)
        
        if not booking.local_id == get_jwt_identity():
            abort(401, message = f'You are not allowed to get the booking [{booking_id}].')
        
        return booking
    
    
    @blp.arguments(BookingAdminSchema)
    @blp.response(404, description='The local was not found. The service was not found. The worker was not found.')
    @blp.response(400, description='Invalid date format.')
    @blp.response(401, description='You are not allowed to update the booking.')
    @blp.response(409, description='There is already a booking in that time. The worker is not available. The services must be from the same work group. The worker must be from the same work group that the services. The local is not available. The date is in the past.')
    @blp.response(201, NewBookingSchema)
    @jwt_required(refresh=True)
    def put(self, booking_data, booking_id): # TODO : test change status
        """
        Updates a booking.
        """
        
        booking = BookingModel.query.get(booking_id)    
                
        if not booking:
            abort(404, message = f'The booking [{booking_id}] was not found.')
                
        if booking.local_id != get_jwt_identity():
            abort(401, message = f'You are not allowed to update the booking [{booking_id}].')
                
        try:
            return createOrUpdateBooking(booking_data, booking.local_id, bookingModel=booking)
        except (StatusNotFoundException, WeekdayNotFoundException) as e:
            abort(500, message = str(e))
        except ModelNotFoundException as e:
            abort(404, message = str(e))
        except ValueError as e:
            abort(400, message = str(e))
        except (PastDateException, WrongServiceWorkGroupException, LocalUnavailableException, WrongWorkerWorkGroupException, WorkerUnavailableException, AlredyBookingExceptionException) as e:
            abort(409, message = str(e))
        except Exception as e:
            traceback.print_exc()
            rollback()
            abort(500, message = str(e) if DEBUG else 'Could not create the booking.')   
    
    @blp.response(404, description='The booking was not found.')
    @blp.response(401, description='You are not allowed to delete the booking.')
    @blp.response(204, description='The booking was deleted.')
    @jwt_required(refresh=True)
    def delete(self, booking_id):
        """
        Delete a booking.
        """
        
        booking = BookingModel.query.get_or_404(booking_id)
        
        if not booking.local_id == get_jwt_identity():
            abort(401, message = f'You are not allowed to delete the booking [{booking_id}].')
        
        try:
            deleteAndCommit()
            return {}
        except SQLAlchemyError as e:
            traceback.print_exc()
            rollback()
            abort(500, message = str(e) if DEBUG else 'Could not delete the booking.')
           
@blp.route('')
class BookingSession(MethodView):
    
    @blp.arguments(BookingSessionParams, location='query')
    @blp.response(404, description='The booking was not found.')
    @blp.response(400, description='No session token provided.')
    @blp.response(401, description='The session token is invalid.')
    @blp.response(200, BookingSchema)
    def get(self):
        """
        Retrieves a booking session.
        """
        return getBookingBySession(request.args.get(SESSION_GET, None))
    
    @blp.arguments(BookingSessionParams, location='query')
    @blp.arguments(BookingSchema)
    @blp.response(404, description='The local was not found. The service was not found. The worker was not found. The booking was not found.')
    @blp.response(400, description='Invalid date format. No session token provided.')
    @blp.response(401, description='The session token is invalid.')
    @blp.response(409, description='There is already a booking in that time. The worker is not available. The services must be from the same work group. The worker must be from the same work group that the services. The local is not available. The date is in the past.')
    @blp.response(201, NewBookingSchema)
    def put(self, booking_data):
        """
        Updates a booking session.
        """
        
        booking = getBookingBySession(request.args.get(SESSION_GET, None))        
                
        try:
            return createOrUpdateBooking(booking_data, booking.local_id, bookingModel=booking)
        except (StatusNotFoundException, WeekdayNotFoundException) as e:
            abort(500, message = str(e))
        except ModelNotFoundException as e:
            abort(404, message = str(e))
        except ValueError as e:
            abort(400, message = str(e))
        except (PastDateException, WrongServiceWorkGroupException, LocalUnavailableException, WrongWorkerWorkGroupException, WorkerUnavailableException, AlredyBookingExceptionException) as e:
            abort(409, message = str(e))
        except Exception as e:
            traceback.print_exc()
            rollback()
            abort(500, message = str(e) if DEBUG else 'Could not create the booking.')   
    
    @blp.arguments(BookingSessionParams, location='query')
    @blp.response(404, description='The booking was not found.')
    @blp.response(400, description='No session token provided.')
    @blp.response(401, description='The session token is invalid.')
    @blp.response(204, description='The booking was deleted.')
    def delete(self):
        """
        Deletes a booking session.
        """
        booking = getBookingBySession(request.args.get(SESSION_GET, None))
        
        try:
            deleteAndCommit(booking)
        except SQLAlchemyError as e:
            traceback.print_exc()
            rollback()
            abort(500, message = str(e) if DEBUG else 'Could not delete the booking.')
            
        return {}
        
@blp.route('confirm')
class BookingConfirm(MethodView):
    
    @blp.arguments(BookingSessionParams, location='query')
    @blp.response(404, description='The booking was not found.')
    @blp.response(400, description='No session token provided.')
    @blp.response(401, description='The session token is invalid.')
    @blp.response(200, BookingSchema)
    def get(self):
        """
        Confirms a booking. Change the status to confirmed.
        """
        booking = getBookingBySession(request.args.get(SESSION_GET, None))
        
        status = StatusModel.query.filter_by(status=CONFIRMED_STATUS).first()
        
        if not status:
            abort(500, message='The status was not found.')
            
        booking.status_id = status.id
        
        try:
            addAndCommit(booking)
        except SQLAlchemyError as e:
            traceback.print_exc()
            rollback()
            abort(500, message = str(e) if DEBUG else 'Could not confirm the booking.')
            
        return booking
    
@blp.route('status')
class Status(MethodView):
    
    @blp.response(200, StatusSchema(many=True))
    def get(self):
        """
        Retrieves all status
        """        
        return StatusModel.query.all()