from datetime import datetime, timedelta
import random
from flask import request
from flask.views import MethodView
from flask_smorest import Blueprint, abort
from helpers.BookingController import calculatEndTimeBooking, cancelBooking, createOrUpdateBooking, getBookings, getBookingBySession as getBookingBySessionHelper
from helpers.ConfirmBookingController import start_waiter_booking_status
from helpers.DataController import getDataRequest, getMonthDataRequest, getWeekDataRequest
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
from helpers.security import decodeJWT, decodeToken, generateTokens
from models.booking import BookingModel
from models.local import LocalModel
from db import addAndFlush, addAndCommit, commit, deleteAndFlush, deleteAndCommit, flush, rollback
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy.exc import SQLAlchemyError, OperationalError
import traceback

from globals import ADMIN_IDENTITY, ADMIN_ROLE, CANCELLED_STATUS, DEBUG, CONFIRMED_STATUS, DONE_STATUS, PENDING_STATUS, SESSION_GET, STATUS_LIST_GET, USER_ROLE, WEEK_DAYS, WORK_GROUP_ID_GET, WORKER_ID_GET
from models.service import ServiceModel
from models.session_token import SessionTokenModel
from models.status import StatusModel
from models.weekday import WeekdayModel
from models.worker import WorkerModel
from schema import BookingAdminParams, BookingAdminSchema, BookingAdminWeekParams, BookingParams, BookingSchema, BookingSessionParams, BookingWeekParams, CommentSchema, NewBookingSchema, PublicBookingSchema, StatusSchema

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
    def get(self, _, local_id):
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
    def get(self, _, local_id):
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

@blp.route('/local/<string:local_id>/month')
class SeePublicBookingMonth(MethodView):
    
    @blp.arguments(BookingWeekParams, location='query')
    @blp.response(404, description='The local was not found')
    @blp.response(422, description='Unspecified date.')
    @blp.response(204, description='The local does not have bookings.')
    @blp.response(200, PublicBookingSchema(many=True))
    def get(self, _, local_id):
        """
        Retrieves public bookings from a month
        """
        
        try:
            datetime_init, datetime_end = getMonthDataRequest(request)
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
    def get(self, _):
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
        
        client_filter = {
            'name': request.args.get('name', None),
            'email': request.args.get('email', None),
            'tlf': request.args.get('tlf', None)
        }
        
        bookings = getBookings(get_jwt_identity(), datetime_init, datetime_end, status=status, worker_id=worker_id, work_group_id=work_group_id, client_filter=client_filter)
                
        return bookings
    
@blp.route('/all/week')
class SeePublicBookingWeek(MethodView):
    
    @blp.arguments(BookingAdminWeekParams, location='query')
    @blp.response(404, description='The local was not found')
    @blp.response(422, description='Unspecified date.')
    @blp.response(204, description='The local does not have bookings.')
    @blp.response(200, BookingSchema(many=True))
    @jwt_required(refresh=True)
    def get(self, _):
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
            
        client_filter = {
            'name': request.args.get('name', None),
            'email': request.args.get('email', None),
            'tlf': request.args.get('tlf', None)
        }
                        
        return getBookings(get_jwt_identity(), datetime_init, datetime_end, status=status, worker_id=worker_id, work_group_id=work_group_id, client_filter=client_filter)
    
@blp.route('/all/month')
class SeePublicBookingMonth(MethodView):
    
    @blp.arguments(BookingAdminWeekParams, location='query')
    @blp.response(404, description='The local was not found')
    @blp.response(422, description='Unspecified date.')
    @blp.response(204, description='The local does not have bookings.')
    @blp.response(200, BookingSchema(many=True))
    @jwt_required(refresh=True)
    def get(self, _):
        """
        Retrieves private data bookings from a month
        """
        
        try:
            datetime_init, datetime_end = getMonthDataRequest(request)
        except ValueError as e:
            abort(400, message=str(e))
        except UnspecifedDateException as e:
            abort(422, message=str(e))    
            
        worker_id = request.args.get(WORKER_ID_GET, None)
        work_group_id = request.args.get(WORK_GROUP_ID_GET, None)
        status = request.args.get(STATUS_LIST_GET, None)
        if status:
            status = status.split(',')
                 
        client_filter = {
            'name': request.args.get('name', None),
            'email': request.args.get('email', None),
            'tlf': request.args.get('tlf', None)
        }
                        
        return getBookings(get_jwt_identity(), datetime_init, datetime_end, status=status, worker_id=worker_id, work_group_id=work_group_id, client_filter=client_filter)
     

@blp.route('/local/<string:local_id>')
class Booking(MethodView):
    
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
            
            timeout = start_waiter_booking_status(booking.id)
                
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
    @blp.response(200, BookingSchema)
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
            
        booking_data['status'] = booking_data.pop('new_status')
                
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
    def get(self, params):
        """
        Retrieves a booking session.
        """
        booking = getBookingBySession(params[SESSION_GET])
        
        if booking.status.status == DONE_STATUS:
            token = SessionTokenModel.query.get_or_404(decodeToken(params[SESSION_GET])['token'])
            try:
                deleteAndCommit(token)
            except SQLAlchemyError as e:
                traceback.print_exc()
                rollback()
            abort(409, message = f"The booking is '{booking.status.name}'.")       
            
        return booking 
    
    #TODO : poder insertar reservas en pasado con admin token
    
    @blp.arguments(BookingSessionParams, location='query')
    @blp.arguments(BookingSchema)
    @blp.response(404, description='The local was not found. The service was not found. The worker was not found. The booking was not found.')
    @blp.response(400, description='Invalid date format. No session token provided.')
    @blp.response(401, description='The session token is invalid.')
    @blp.response(409, description='There is already a booking in that time. The worker is not available. The services must be from the same work group. The worker must be from the same work group that the services. The local is not available. The date is in the past.')
    @blp.response(200, BookingSchema)
    def put(self, params, booking_data):
        """
        Updates a booking session.
        """
                
        booking = getBookingBySession(params[SESSION_GET])        

        if booking.status.status == CANCELLED_STATUS or booking.status.status == DONE_STATUS:
            abort(409, message = f"The booking is '{booking.status.name}'.")

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
    @blp.arguments(CommentSchema)
    @blp.response(404, description='The booking was not found.')
    @blp.response(400, description='No session token provided.')
    @blp.response(401, description='The session token is invalid.')
    @blp.response(204, description='The booking was deleted.')
    def delete(self, params, data):
        """
        Deletes a booking session.
        """
        booking = getBookingBySession(params[SESSION_GET])
        
        if 'comment' in data:
            booking.comment = data['comment']
        
        try:
            cancelBooking(booking)
        except SQLAlchemyError as e:
            traceback.print_exc()
            abort(500, message = str(e) if DEBUG else 'Could not delete the booking.')
            
        return {}
        
@blp.route('confirm')
class BookingConfirm(MethodView):
    
    @blp.arguments(BookingSessionParams, location='query')
    @blp.response(404, description='The booking was not found.')
    @blp.response(400, description='No session token provided.')
    @blp.response(401, description='The session token is invalid.')
    @blp.response(200, BookingSchema)
    def get(self, params):
        """
        Confirms a booking. Change the status to confirmed.
        """
        booking = getBookingBySession(params[SESSION_GET])
        
        if not booking.status.status == PENDING_STATUS:
            status = StatusModel.query.get(booking.status_id)
            if not status: abort(500, message='The status was not found.')
            abort(409, message=f"The booking is '{status.name}'.")
        
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
    
    
@blp.route('admin')
class BookingAdmin(MethodView):
    
    @blp.arguments(BookingSchema)
    @blp.response(404, description='The token does not exist.')
    @blp.response(403, description='You are not allowed to use this endpoint.')
    @blp.response(401, description='Missing Authorization Header.')
    @blp.response(201, NewBookingSchema)
    def post(self, booking_data):
        """
        Creates a new booking.
        """
        token_header = request.headers.get('Authorization')

        if not token_header or not token_header.startswith('Bearer '):
            return abort(401, message='Missing Authorization Header')
        
        token = token_header.split(' ', 1)[1]
        
        identity = decodeJWT(token)['sub']
        id = decodeJWT(token)['token']
                
        token = SessionTokenModel.query.get_or_404(id)
        
        if identity != ADMIN_IDENTITY or token.user_session.user != ADMIN_ROLE:
            abort(403, message = 'You are not allowed to use this endpoint.')
            
        services_ids = booking_data.pop('services_ids')
        services = [ServiceModel.query.get_or_404(id) for id in services_ids]

        if 'worker_id' not in booking_data:
            abort(400, message = 'The worker_id is required.')
            
        worker = WorkerModel.query.get_or_404(booking_data.pop('worker_id'))

        status = StatusModel.query.filter_by(status=CONFIRMED_STATUS).first()
        
        booking = BookingModel(**booking_data)
        
        booking.services = services
        booking.worker = worker
        booking.status = status
        booking = calculatEndTimeBooking(booking)
        
        try:
            addAndFlush(booking)
            timeout = 0
            
            exp = timedelta(minutes=0)
            
            token = generateTokens(booking.id, booking.local_id, refresh_token=True, expire_refresh=exp, user_role=USER_ROLE)
            
            commit()
            
            return {
                "booking": booking,
                "timeout": timeout,
                "session_token": token
            }
        except SQLAlchemyError as e:
            traceback.print_exc()
            rollback()
            abort(500, message = str(e) if DEBUG else 'Could not create the booking.')
        
        
        
        