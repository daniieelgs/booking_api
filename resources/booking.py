from datetime import datetime, timedelta
import random
from flask import request
from flask.views import MethodView
from flask_smorest import Blueprint, abort
from helpers.BookingController import createOrUpdateBooking, getBookings, getBookingBySession as getBookingBySessionHelper
from helpers.ConfirmBookingController import start_waiter_booking_status
from helpers.TimetableController import getTimetable
from helpers.error.BookingError.AlredyBookingException import AlredyBookingExceptionException
from helpers.error.BookingError.LocalUnavailableException import LocalUnavailableException
from helpers.error.BookingError.PastDateException import PastDateException
from helpers.error.BookingError.WorkerUnavailable import WorkerUnavailableException
from helpers.error.BookingError.WrongServiceWorkGroupException import WrongServiceWorkGroupException
from helpers.error.BookingError.WrongWorkerWorkGroupException import WrongWorkerWorkGroupException
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

from globals import DEBUG, CONFIRMED_STATUS, PENDING_STATUS, USER_ROLE, WEEK_DAYS
from models.service import ServiceModel
from models.session_token import SessionTokenModel
from models.status import StatusModel
from models.weekday import WeekdayModel
from models.worker import WorkerModel
from schema import BookingSchema, NewBookingSchema, PublicBookingSchema, StatusSchema

blp = Blueprint('booking', __name__, description='Timetable CRUD')

# TODO : documentar parametro GET
# TODO : modificar estados de las reservas

DEFAULT_FORMAT = '%Y-%m-%d %H:%M:%S'
DEFAULT_FORMAT_DATA = '%Y-%m-%d'

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
    
    @blp.response(404, description='The local was not found')
    @blp.response(422, description='Unspecified date.')
    @blp.response(204, description='The local does not have bookings.')
    @blp.response(200, PublicBookingSchema(many=True))
    def get(self, local_id):
        """
        Retrieves public bookings from specific DateTime.
        """      
        
        date = request.args.get('date', None)
        datetime_init = request.args.get('datetime_init', None)
        datetime_end = request.args.get('datetime_end', None)
        
        try:
            if date:
                format = request.args.get('format', DEFAULT_FORMAT_DATA)
                date = datetime.strptime(date, format)
                datetime_init = datetime.combine(date, datetime.min.time())
                datetime_end = datetime.combine(date, datetime.max.time())
            elif datetime_init and datetime_end:
                format = request.args.get('format', DEFAULT_FORMAT)
                datetime_init = datetime.strptime(datetime_init, format)
                datetime_end = datetime.strptime(datetime_end, format)
            else:
                abort(422, message='Unspecified date.')
        except ValueError:
            abort(400, message='Invalid date format.')        
        
        worker_id = request.args.get('worker_id', None)
        work_group_id = request.args.get('work_group_id', None)
        
        bookings = getBookings(local_id, datetime_init, datetime_end, status=[CONFIRMED_STATUS, PENDING_STATUS], worker_id=worker_id, work_group_id=work_group_id)
        
        print(bookings)
        
        return bookings
    
@blp.route('/local/<string:local_id>/week')
class SeePublicBookingWeek(MethodView):
    
    @blp.response(404, description='The local was not found')
    @blp.response(422, description='Unspecified date.')
    @blp.response(204, description='The local does not have bookings.')
    @blp.response(200, PublicBookingSchema(many=True))
    def get(self, local_id):
        
        date = request.args.get('date', None)
        format = request.args.get('format', DEFAULT_FORMAT_DATA)
        
        datetime_init = None
        datetime_end = None
        
        try:
            if date:
                date = datetime.strptime(date, format)
                week_day = date.weekday()
                date = date - timedelta(days=week_day)
                datetime_init = datetime.combine(date, datetime.min.time())
                datetime_end = datetime.combine(date, datetime.max.time()) + timedelta(days=7)
            else:
                abort(422, message='Unspecified date.')
        except ValueError:
            abort(400, message='Invalid date format.')
            
        worker_id = request.args.get('worker_id', None)
        work_group_id = request.args.get('work_group_id', None)
                        
        return getBookings(local_id, datetime_init, datetime_end, status=[CONFIRMED_STATUS, PENDING_STATUS], worker_id=worker_id, work_group_id=work_group_id)
    
@blp.route('/local/<string:local_id>')
class Booking(MethodView):
    
    # TODO : comprobar timetable del local
    # TODO : comprobar que el trabajador tiene el horario disponible
    # TODO : definir comportamiento al eliminar un servicio, trabajador o work group y al actualizar el timetable
    # TODO : ver las reservas que tiene un trabajador
    # TODO : definir comportamiento al cambiar un trabajador de work group o un servicio de work group
    # TODO : crear sesion token para modificar la reserva
    @blp.arguments(BookingSchema)
    @blp.response(404, description='The local was not found. The service was not found. The worker was not found.')
    @blp.response(400, description='Invalid date format.')
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
             
           
@blp.route('')
class BookingSession(MethodView):
    
    @blp.response(404, description='The booking was not found.')
    @blp.response(400, description='No session token provided.')
    @blp.response(401, description='The session token is invalid.')
    @blp.response(200, BookingSchema)
    def get(self):
        """
        Retrieves a booking session.
        """
        return getBookingBySession(request.args.get('session', None))
    
    @blp.arguments(BookingSchema)
    @blp.response(404, description='The booking was not found.')
    @blp.response(400, description='No session token provided.')
    @blp.response(401, description='The session token is invalid.')
    @blp.response(200, BookingSchema)
    def put(self, booking_data):
        """
        Updates a booking session.
        """
        
        booking = getBookingBySession(request.args.get('session', None))        
                
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
    @blp.response(400, description='No session token provided.')
    @blp.response(401, description='The session token is invalid.')
    @blp.response(204, description='The booking was deleted.')
    def delete(self):
        """
        Deletes a booking session.
        """
        booking = getBookingBySession(request.args.get('session', None))
        
        try:
            deleteAndCommit(booking)
        except SQLAlchemyError as e:
            traceback.print_exc()
            rollback()
            abort(500, message = str(e) if DEBUG else 'Could not delete the booking.')
            
        return {}
        
@blp.route('confirm')
class BookingConfirm(MethodView):
    
    @blp.response(404, description='The booking was not found.')
    @blp.response(400, description='No session token provided.')
    @blp.response(401, description='The session token is invalid.')
    @blp.response(200, BookingSchema)
    def get(self):
        """
        Confirms a booking. Change the status to confirmed.
        """
        booking = getBookingBySession(request.args.get('session', None))
        
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