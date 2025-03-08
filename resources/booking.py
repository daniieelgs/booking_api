from datetime import datetime, timedelta
import json
from flask import request
from flask.views import MethodView
from flask_smorest import Blueprint, abort
from helpers.error.ClosedDaysError.ClosedDayException import ClosedDayException
from jwt import ExpiredSignatureError
from helpers.BookingController import calculatEndTimeBooking, calculateExpireBookingToken, cancelBooking, confirmBooking, createOrUpdateBooking, deserializeBooking, getBookings, getBookingBySession as getBookingBySessionHelper, unregisterBooking
from helpers.BookingEmailController import send_cancelled_mail_async, send_confirmed_mail_async, send_updated_mail_async, start_waiter_booking_status
from helpers.DataController import getDataRequest, getMonthDataRequest, getWeekDataRequest
from helpers.DatetimeHelper import now
from helpers.EmailController import send_confirm_booking_mail
from helpers.LoggingMiddleware import log_route
from helpers.TimetableController import getTimetable
from helpers.error.BookingError.AlredyBookingException import AlredyBookingExceptionException
from helpers.error.BookingError.BookingNotFoundError import BookingNotFoundException
from helpers.error.BookingError.LocalUnavailableException import LocalUnavailableException
from helpers.error.DataError.PastDateException import PastDateException
from helpers.error.BookingError.WorkerUnavailable import WorkerUnavailableException
from helpers.error.BookingError.WrongServiceWorkGroupException import WrongServiceWorkGroupException
from helpers.error.BookingError.WrongWorkerWorkGroupException import WrongWorkerWorkGroupException
from helpers.error.DataError.UnspecifedDateException import UnspecifedDateException
from helpers.error.LocalError.LocalNotFoundException import LocalNotFoundException
from helpers.error.LocalError.LocalOverloadedException import LocalOverloadedException
from helpers.error.ModelNotFoundException import ModelNotFoundException
from helpers.error.SecurityError.InvalidTokenException import InvalidTokenException
from helpers.error.SecurityError.NoTokenProvidedException import NoTokenProvidedException
from helpers.error.SecurityError.TokenNotFound import TokenNotFoundException
from helpers.error.StatusError.StatusNotFoundException import StatusNotFoundException
from helpers.error.WeekdayError.WeekdayNotFoundException import WeekdayNotFoundException
from helpers.security import decodeJWT, decodeToken, generateTokens, getTokenId
from models.booking import BookingModel
from db import addAndFlush, addAndCommit, commit, deleteAndCommit, deleteAndFlush, rollback
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy.exc import SQLAlchemyError, OperationalError
import traceback

from globals import ADMIN_IDENTITY, ADMIN_ROLE, CANCELLED_STATUS, DEBUG, CONFIRMED_STATUS, DONE_STATUS, PENDING_STATUS, SESSION_GET, STATUS_LIST_GET, USER_ROLE, WEEK_DAYS, WORK_GROUP_ID_GET, WORKER_ID_GET, log
from models.local import LocalModel
from models.service import ServiceModel
from models.service_booking import ServiceBookingModel
from models.session_token import SessionTokenModel
from models.status import StatusModel
from models.timetable import TimetableModel
from models.weekday import WeekdayModel
from models.worker import WorkerModel
from schema import BookingAdminListSchema, BookingAdminParams, BookingAdminPatchSchema, BookingAdminSchema, BookingAdminWeekParams, BookingListSchema, BookingParams, BookingPatchSchema, BookingSchema, BookingSessionParams, BookingWeekParams, CommentSchema, NewBookingSchema, NotifyParams, PublicBookingListSchema, PublicBookingSchema, StatusSchema, UpdateParams

blp = Blueprint('booking', __name__, description='Control de reservas.')

def getBookingBySession(token):
    try:
        return getBookingBySessionHelper(token)
    except NoTokenProvidedException as e:
        abort(400, message=str(e))
    except InvalidTokenException as e:
        abort(401, message=str(e))
    except ExpiredSignatureError as e:
        abort(403, message="The token has expired.")
    except TokenNotFoundException as e:
        abort(404, message=str(e))
    except BookingNotFoundException as e:
        abort(404, message=str(e))
    except Exception as e:
        traceback.print_exc()
        abort(500, message=str(e) if DEBUG else 'Could not get the booking.')

def patchBooking(booking, booking_data, admin = False):
    
    booking_deserialized = deserializeBooking(booking)
        
    for key, value in booking_data.items():
        booking_deserialized[key] = value
        
    booking_deserialized.pop('status_id', None)
        
    if 'comment' not in booking_data:
        booking_deserialized.pop('comment', None)
        
    if 'worker_id' not in booking_data:
        booking_deserialized.pop('worker_id', None)
        
    if not admin:
        booking_deserialized.pop('status', None)
        
    return booking_deserialized

@blp.route('/local/<string:local_id>')
class SeePublicBooking(MethodView):
    
    @log_route
    @blp.arguments(BookingParams, location='query')
    @blp.response(404, description='El local no existe.')
    @blp.response(422, description='Fecha no especificada.')
    @blp.response(204, description='El local no tiene reservas para la fecha indicada.')
    @blp.response(200, PublicBookingListSchema)
    def get(self, params, local_id, _uuid = None):
        """
        Devuelve las reservas públicas de una fecha específica.
        """      
        
        try:
            datetime_init, datetime_end = getDataRequest(request)
                        
            worker_id = request.args.get(WORKER_ID_GET, None)
            work_group_id = request.args.get(WORK_GROUP_ID_GET, None)
            
            log(f"Searching bookings for local '{local_id}' in date '{datetime_init}' to '{datetime_end}'. [worker_id: {worker_id}, work_group_id: {work_group_id}]", uuid=_uuid)
            
            bookings = getBookings(local_id, datetime_init, datetime_end, status=[CONFIRMED_STATUS, PENDING_STATUS], worker_id=worker_id, work_group_id=work_group_id, _uuid = _uuid)        
        except ValueError as e:
            log(f"Invalid date format.", uuid=_uuid, level='WARNING', error=e)
            abort(400, message=str(e))
        except LocalNotFoundException as e:
            log(f"Local '{local_id}' not found.", uuid=_uuid, level='WARNING', error=e)
            abort(404, message=str(e))
        except UnspecifedDateException as e:
            log(f"Date not specified.", uuid=_uuid, level='WARNING', error=e)
            abort(422, message=str(e))    
                
        free = params['free'] if 'free' in params else False
                
        if free:
            week_day = WeekdayModel.query.filter_by(weekday=WEEK_DAYS[datetime_init.weekday()]).first()
            timetable_init = getTimetable(local_id, week_day.id, datetime_init)
            timetable_end = getTimetable(local_id, week_day.id, datetime_end)
            init = timetable_init[0].opening_time if timetable_init else None
            end = timetable_end[-1].closing_time if timetable_end else None
            print("Timetables: ", init, end)
            
                
        return {"bookings": bookings, "total": len(bookings)}
    
@blp.route('/local/<string:local_id>/week')
class SeePublicBookingWeek(MethodView):
    
    @log_route
    @blp.arguments(BookingWeekParams, location='query')
    @blp.response(404, description='El local no existe.')
    @blp.response(422, description='Fecha no especificada.')
    @blp.response(204, description='El local no tiene reservas para la fecha indicada.')
    @blp.response(200, PublicBookingListSchema)
    def get(self, _, local_id, _uuid = None):
        """
        Devuelve las reservas públicas de una semana.
        """
        
        try:
            datetime_init, datetime_end = getWeekDataRequest(request)
                                
            worker_id = request.args.get(WORKER_ID_GET, None)
            work_group_id = request.args.get('work_group_id', None)
                
            log(f"Searching bookings for local '{local_id}' in date '{datetime_init}' to '{datetime_end}'. [worker_id: {worker_id}, work_group_id: {work_group_id}]", uuid=_uuid)
                
            bookings = getBookings(local_id, datetime_init, datetime_end, status=[CONFIRMED_STATUS, PENDING_STATUS], worker_id=worker_id, work_group_id=work_group_id)
        except ValueError as e:
            log(f"Invalid date format.", uuid=_uuid, level='WARNING', error=e)
            abort(400, message=str(e))
        except LocalNotFoundException as e:
            log(f"Local '{local_id}' not found.", uuid=_uuid, level='WARNING', error=e)
            abort(404, message=str(e))
        except UnspecifedDateException as e:
            log(f"Date not specified.", uuid=_uuid, level='WARNING', error=e)
            abort(422, message=str(e))    
                  
        return {"bookings": bookings, "total": len(bookings)} 
    
@blp.route('/local/<string:local_id>/month')
class SeePublicBookingMonth(MethodView):
    
    @log_route
    @blp.arguments(BookingWeekParams, location='query')
    @blp.response(404, description='El local no existe.')
    @blp.response(422, description='Fecha no especificada.')
    @blp.response(204, description='El local no tiene reservas para la fecha indicada.')
    @blp.response(200, PublicBookingListSchema)
    def get(self, _, local_id, _uuid = None):
        """
        Devuelve las reservas públicas de un mes.
        """
        
        try:
            datetime_init, datetime_end = getMonthDataRequest(request)
            
            worker_id = request.args.get(WORKER_ID_GET, None)
            work_group_id = request.args.get('work_group_id', None)
                
            log(f"Searching bookings for local '{local_id}' in date '{datetime_init}' to '{datetime_end}'. [worker_id: {worker_id}, work_group_id: {work_group_id}]", uuid=_uuid)
                
            bookings = getBookings(local_id, datetime_init, datetime_end, status=[CONFIRMED_STATUS, PENDING_STATUS], worker_id=worker_id, work_group_id=work_group_id)
            
        except ValueError as e:
            log(f"Invalid date format.", uuid=_uuid, level='WARNING', error=e)
            abort(400, message=str(e))
        except LocalNotFoundException as e:
            log(f"Local '{local_id}' not found.", uuid=_uuid, level='WARNING', error=e)
            abort(404, message=str(e))
        except UnspecifedDateException as e:
            log(f"Date not specified.", uuid=_uuid, level='WARNING', error=e)
            abort(422, message=str(e))    
                   
        return {"bookings": bookings, "total": len(bookings)}  
    
@blp.route('/all')
class SeeBookingWeek(MethodView):
    
    @log_route
    @blp.arguments(BookingAdminParams, location='query')
    @blp.response(404, description='El local no existe.')
    @blp.response(422, description='Fecha no especificada.')
    @blp.response(204, description='El local no tiene reservas para la fecha indicada.')
    @blp.response(200, BookingAdminListSchema)
    @jwt_required(refresh=True)
    def get(self, _, _uuid = None):
        """
        Devuelve las reservas privadas de una fecha específica.
        """      
        
        try:
            datetime_init, datetime_end = getDataRequest(request)
            
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
            
            log(f"Searching bookings for local '{get_jwt_identity()}' in date '{datetime_init}' to '{datetime_end}'. [worker_id: {worker_id}, work_group_id: {work_group_id}, status: {status}, client_filter: {json.dumps(client_filter)}]", uuid=_uuid)
            
            bookings = getBookings(get_jwt_identity(), datetime_init, datetime_end, status=status, worker_id=worker_id, work_group_id=work_group_id, client_filter=client_filter)
            
        except ValueError as e:
            log(f"Invalid date format.", uuid=_uuid, level='WARNING', error=e)
            abort(400, message=str(e))
        except LocalNotFoundException as e:
            log(f"Local '{get_jwt_identity()}' not found.", uuid=_uuid, level='WARNING', error=e)
            abort(404, message=str(e))
        except UnspecifedDateException as e:
            log(f"Date not specified.", uuid=_uuid, level='WARNING', error=e)
            abort(422, message=str(e))     
                                
        return {"bookings": bookings, "total": len(bookings)}  
       
@blp.route('/all/week')
class SeeBookingWeek(MethodView):
    
    @log_route
    @blp.arguments(BookingAdminWeekParams, location='query')
    @blp.response(404, description='El local no existe.')
    @blp.response(422, description='Fecha no especificada.')
    @blp.response(204, description='El local no tiene reservas para la fecha indicada.')
    @blp.response(200, BookingAdminListSchema)
    @jwt_required(refresh=True)
    def get(self, _, _uuid = None):
        """
        Devuelve las reservas privadas de una semana.
        """
        
        try:
            datetime_init, datetime_end = getWeekDataRequest(request)
            
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
                
            log(f"Searching bookings for local '{get_jwt_identity()}' in date '{datetime_init}' to '{datetime_end}'. [worker_id: {worker_id}, work_group_id: {work_group_id}, status: {status}, client_filter: {json.dumps(client_filter)}]", uuid=_uuid)
                
            bookings = getBookings(get_jwt_identity(), datetime_init, datetime_end, status=status, worker_id=worker_id, work_group_id=work_group_id, client_filter=client_filter)
            
        except ValueError as e:
            log(f"Invalid date format.", uuid=_uuid, level='WARNING', error=e)
            abort(400, message=str(e))
        except LocalNotFoundException as e:
            log(f"Local '{get_jwt_identity()}' not found.", uuid=_uuid, level='WARNING', error=e)
            abort(404, message=str(e))
        except UnspecifedDateException as e:
            log(f"Date not specified.", uuid=_uuid, level='WARNING', error=e)
            abort(422, message=str(e))    
                                                
        return {"bookings": bookings, "total": len(bookings)}  
    
@blp.route('/all/month')
class SeeBookingMonth(MethodView):
    
    @log_route
    @blp.arguments(BookingAdminWeekParams, location='query')
    @blp.response(404, description='El local no existe.')
    @blp.response(422, description='Fecha no especificada.')
    @blp.response(204, description='El local no tiene reservas para la fecha indicada.')
    @blp.response(200, BookingAdminListSchema)
    @jwt_required(refresh=True)
    def get(self, _, _uuid = None):
        """
        Devuelve las reservas privadas de un mes.
        """
        
        try:
            datetime_init, datetime_end = getMonthDataRequest(request)
            
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
                
            log(f"Searching bookings for local '{get_jwt_identity()}' in date '{datetime_init}' to '{datetime_end}'. [worker_id: {worker_id}, work_group_id: {work_group_id}, status: {status}, client_filter: {json.dumps(client_filter)}]", uuid=_uuid)
                
            bookings = getBookings(get_jwt_identity(), datetime_init, datetime_end, status=status, worker_id=worker_id, work_group_id=work_group_id, client_filter=client_filter)
            
        except ValueError as e:
            log(f"Invalid date format.", uuid=_uuid, level='WARNING', error=e)
            abort(400, message=str(e))
        except LocalNotFoundException as e:
            log(f"Local '{get_jwt_identity()}' not found.", uuid=_uuid, level='WARNING', error=e)
            abort(404, message=str(e))
        except UnspecifedDateException as e:
            log(f"Date not specified.", uuid=_uuid, level='WARNING', error=e)
            abort(422, message=str(e))    
        
        return {"bookings": bookings, "total": len(bookings)}  

@blp.route('/local/<string:local_id>')
class Booking(MethodView):
    
    @log_route
    @blp.arguments(BookingSchema)
    @blp.response(404, description='El local no existe, el servicio no existe o el trabajador no existe.')
    @blp.response(400, description='Formato de fecha no válido o no se ha proporcionado el token de sesión.')
    @blp.response(409, description='Ya existe una reserva en ese tiempo. El trabajador no está disponible. Los servicios deben ser del mismo grupo de trabajo. El trabajador debe ser del mismo grupo de trabajo que los servicios. El local no está disponible. La fecha está en el pasado.')
    @blp.response(201, NewBookingSchema)
    def post(self, new_booking, local_id, _uuid = None):
        """
        Crea una nueva reserva.
        """
                
        local = LocalModel.query.get_or_404(local_id)
        
        log(f"Creating a new booking for local '{local.name}'.", uuid=_uuid)
        log(f"<| Last UUID Log: [NULL] |>")
        
        session = None
        
        try:
            
            booking, unregisterFromCache = createOrUpdateBooking(new_booking, local=local, commit=False, _uuid=_uuid)
                        
            log(f"Booking created for local '{local.name}'.", uuid=_uuid)
            log(f"Generating booking token for local '{local.name}'.", uuid=_uuid)
                        
            exp:timedelta = calculateExpireBookingToken(booking.datetime_init, local.location)
                        
            token = generateTokens(booking.id, booking.local_id, refresh_token=True, expire_refresh=exp, user_role=USER_ROLE)
                        
            booking.email_confirm = True
            
            booking.uuid_log = _uuid
            
            try:
                log(f"Commiting booking for local '{local.name}'.", uuid=_uuid)            
                commit(session)
            except SQLAlchemyError as e:
                log(f"Error commiting booking for local '{local.name}'. Unregistering from cache", uuid=_uuid, level='ERROR', error=e)
                unregisterFromCache()
                raise e
            
            log("Unregistering from cache.", uuid=_uuid)
            unregisterFromCache()
                        
            log(f"Sending confirmation email for booking '{booking.id}'.", uuid=_uuid)
            email_confirm = send_confirm_booking_mail(local, booking, token, _uuid=_uuid)
                        
            timeout = None
            
            if email_confirm:
                timeout_local = local.local_settings.booking_timeout
                log(f"Starting waiter for booking '{booking.id}' with timeout '{timeout_local}'.", uuid=_uuid)
                timeout = start_waiter_booking_status(booking.id, timeout=timeout_local)
            else:
                
                log(f"Booking '{booking.id}' will not be confirmed by email.", uuid=_uuid)
                
                booking.email_confirm = False
                    
                log(f"Confirming booking '{booking.id}'.", uuid=_uuid)
                confirmBooking(booking, session=session)
                    
                log(f"Sending confirmation email for booking '{booking.id}'.", uuid=_uuid)
                send_confirmed_mail_async(local_id, booking.id, _uuid=_uuid)
                    
                log(f"Commiting booking '{booking.id}'.", uuid=_uuid)
                addAndCommit(booking, session)
              
            if session is not None: session.close()
                    
            return {
                "booking": booking,
                "timeout": timeout,
                "email_confirm": email_confirm,
                "session_token": token
            }
        except (StatusNotFoundException, WeekdayNotFoundException) as e:
            log(f"Error creating booking for local '{local.name}'.", uuid=_uuid, level='ERROR', error=e)
            abort(500, message = str(e))
        except LocalOverloadedException as e:
            log(f"Error creating booking for local '{local.name}'.", uuid=_uuid, level='ERROR', error=e)
            abort(503, message = str(e))
        except ModelNotFoundException as e:
            log(f"Error creating booking for local '{local.name}'.", uuid=_uuid, level='WARNING', error=e)
            abort(404, message = str(e))
        except ValueError as e:
            log(f"Error creating booking for local '{local.name}'.", uuid=_uuid, level='WARNING', error=e)
            abort(400, message = str(e))
        except (PastDateException, WrongServiceWorkGroupException, LocalUnavailableException, ClosedDayException, WrongWorkerWorkGroupException, WorkerUnavailableException, AlredyBookingExceptionException) as e:
            log(f"Error creating booking for local '{local.name}'.", uuid=_uuid, level='WARNING', error=e)
            abort(409, message = str(e))
        except Exception as e:
            log(f"FATAL ERROR. Error creating booking for local '{local.name}'.", uuid=_uuid, level='ERROR', error=e)
            traceback.print_exc()
            rollback(session)
            if session is not None: session.close()
            abort(500, message = str(e) if DEBUG else 'Could not create the booking.')   
             

@blp.route('/<int:booking_id>')
class BookingAdmin(MethodView):
    
    @log_route
    @blp.response(404, description='La reserva no existe.')
    @blp.response(401, description='No tienes permisos para obtener la reserva.')
    @blp.response(200, BookingAdminSchema)
    @jwt_required(refresh=True)
    def get(self, booking_id, _uuid = None):
        """
        Devuelve una reserva. Identificado por el local.
        """
        log(f"Getting booking '{booking_id}'.", uuid=_uuid)
        
        booking = BookingModel.query.get_or_404(booking_id)
                
        if not booking.local_id == get_jwt_identity():
            log(f"Getting booking '{booking_id}'. Unauthorized.", uuid=_uuid, level='WARNING')
            abort(401, message = f'You are not allowed to get the booking [{booking_id}].')
                
        return booking
    
    
    @log_route
    @blp.arguments(UpdateParams, location='query')
    @blp.arguments(BookingAdminSchema)
    @blp.response(404, description='El local no existe, el servicio no existe, el trabajador no existe o la reserva no existe.')
    @blp.response(400, description='Fecha no válida.')
    @blp.response(401, description='No tienes permisos para actualizar la reserva.')
    @blp.response(409, description='Ya existe una reserva en ese tiempo. El trabajador no está disponible. Los servicios deben ser del mismo grupo de trabajo. El trabajador debe ser del mismo grupo de trabajo que los servicios. El local no está disponible. La fecha está en el pasado.')
    @blp.response(200, BookingSchema)
    @jwt_required(refresh=True)
    def put(self, params, booking_data, booking_id, _uuid = None):
        """
        Actualiza una reserva. Por parte del local.
        """
        
        log(f"Updating booking '{booking_id}' by local.", uuid=_uuid)
        
        booking = BookingModel.query.get(booking_id)
        
        force = 'force' in params and params['force']
        notify = 'notify' in params and params['notify']
        
        if not booking:
            log(f"Booking '{booking_id}' not found.", uuid=_uuid, level='WARNING')
            abort(404, message = f'The booking [{booking_id}] was not found.')
                
        log(f"<| Last UUID Log: [{booking.uuid_log}] |>")
        
        booking.uuid_log = _uuid
                
        if booking.local_id != get_jwt_identity():
            log
            abort(401, message = f'You are not allowed to update the booking [{booking_id}].')
            
        booking_data['status'] = booking_data.pop('new_status')
            
        session = None
                
        try:
            booking, _ = createOrUpdateBooking(booking_data, booking.local_id, bookingModel=booking, force=force, _uuid=_uuid)
            
            log(f"Booking '{booking_id}' updated.", uuid=_uuid)
            
            if notify:
                log(f"Sending updated email for booking '{booking_id}'.", uuid=_uuid)
                send_updated_mail_async(booking.local_id, booking.id, _uuid = _uuid)
            
            return booking
        except (StatusNotFoundException, WeekdayNotFoundException) as e:
            log(f"Error updating booking '{booking_id}'.", uuid=_uuid, level='ERROR', error=e)
            abort(500, message = str(e))
        except LocalOverloadedException as e:
            log(f"Error updating booking '{booking_id}'.", uuid=_uuid, level='ERROR', error=e)
            abort(503, message = str(e))
        except ModelNotFoundException as e:
            log(f"Error updating booking '{booking_id}'.", uuid=_uuid, level='WARNING', error=e)
            abort(404, message = str(e))
        except ValueError as e:
            log(f"Error updating booking '{booking_id}'.", uuid=_uuid, level='WARNING', error=e)
            abort(400, message = str(e))
        except (PastDateException, WrongServiceWorkGroupException, LocalUnavailableException, ClosedDayException, WrongWorkerWorkGroupException, WorkerUnavailableException, AlredyBookingExceptionException) as e:
            log(f"Error updating booking '{booking_id}'.", uuid=_uuid, level='WARNING', error=e)
            abort(409, message = str(e))
        except Exception as e:
            log(f"FATAL ERROR. Error updating booking '{booking_id}'.", uuid=_uuid, level='ERROR', error=e)
            traceback.print_exc()
            rollback(session)
            if session is not None: session.close()
            abort(500, message = str(e) if DEBUG else 'Could not create the booking.')
    
    @log_route
    @blp.arguments(UpdateParams, location='query')
    @blp.arguments(BookingAdminPatchSchema)
    @blp.response(404, description='El local no existe, el servicio no existe, el trabajador no existe o la reserva no existe.')
    @blp.response(400, description='Fecha no válida.')
    @blp.response(401, description='No tienes permisos para actualizar la reserva.')
    @blp.response(409, description='Ya existe una reserva en ese tiempo. El trabajador no está disponible. Los servicios deben ser del mismo grupo de trabajo. El trabajador debe ser del mismo grupo de trabajo que los servicios. El local no está disponible. La fecha está en el pasado.')
    @blp.response(200, BookingSchema)
    @jwt_required(refresh=True)
    def patch(self, params, booking_data, booking_id, _uuid = None):
        """
        Actualiza una reserva indicando los campos a modificar. Por parte del local.
        """

        log(f"Updating booking '{booking_id}' by local.", uuid=_uuid)
        
        notify = 'notify' in params and params['notify']
        force = 'force' in params and params['force']
        
        booking = BookingModel.query.get(booking_id)

        log(f"<| Last UUID Log: [{booking.uuid_log}] |>")
        booking.uuid_log = _uuid

        if not booking:
            log(f"Booking '{booking_id}' not found.", uuid=_uuid, level='WARNING')
            abort(404, message = f'The booking [{booking_id}] was not found.')
                
        if booking.local_id != get_jwt_identity():
            log(f"Unauthorized to update booking '{booking_id}'.", uuid=_uuid, level='WARNING')
            abort(401, message = f'You are not allowed to update the booking [{booking_id}].')
            
        if 'new_status' in booking_data: booking_data['status'] = booking_data.pop('new_status')
                        
        booking_data = patchBooking(booking, booking_data, admin = True)
              
        session = None
                
        try:
            booking, _ = createOrUpdateBooking(booking_data, booking.local_id, bookingModel=booking, force=force, _uuid=_uuid)
            
            log(f"Booking '{booking_id}' updated.", uuid=_uuid)
            
            if notify:
                log(f"Sending updated email for booking '{booking_id}'.", uuid=_uuid)
                send_updated_mail_async(booking.local_id, booking.id, _uuid = _uuid)
            
            return booking
        except (StatusNotFoundException, WeekdayNotFoundException) as e:
            log(f"Error updating booking '{booking_id}'.", uuid=_uuid, level='ERROR', error=e)
            abort(500, message = str(e))
        except LocalOverloadedException as e:
            log(f"Error updating booking '{booking_id}'.", uuid=_uuid, level='ERROR', error=e)
            abort(503, message = str(e))
        except ModelNotFoundException as e:
            log(f"Error updating booking '{booking_id}'.", uuid=_uuid, level='WARNING', error=e)
            abort(404, message = str(e))
        except ValueError as e:
            log(f"Error updating booking '{booking_id}'.", uuid=_uuid, level='WARNING', error=e)
            abort(400, message = str(e))
        except (PastDateException, WrongServiceWorkGroupException, LocalUnavailableException, ClosedDayException, WrongWorkerWorkGroupException, WorkerUnavailableException, AlredyBookingExceptionException) as e:
            log(f"Error updating booking '{booking_id}'.", uuid=_uuid, level='WARNING', error=e)
            abort(409, message = str(e))
        except Exception as e:
            log(f"FATAL ERROR. Error updating booking '{booking_id}'.", uuid=_uuid, level='ERROR', error=e)
            traceback.print_exc()
            rollback(session)
            if session is not None: session.close()
            abort(500, message = str(e) if DEBUG else 'Could not create the booking.')  
    
    @log_route
    @blp.response(404, description='La reserva no existe.')
    @blp.response(401, description='No tienes permisos para eliminar la reserva.')
    @blp.response(204, description='La reserva ha sido eliminada.')
    @jwt_required(refresh=True)
    def delete(self, booking_id, _uuid = None):
        """
        Elimina una reserva. WARNING: No se recomienda ya que, no se puede deshacer. Si se desea cancelar una reserva, se recomienda cambiar el estado de la reserva o bien utilizar el endpoint para cancelar una reserva [cancel/{booking_id}].
        """
        
        log(f"Deleting booking '{booking_id}'.", uuid=_uuid)
        
        booking = BookingModel.query.get_or_404(booking_id)
        
        log(f"<| Last UUID Log: [{booking.uuid_log}] |>")
        booking.uuid_log = _uuid
        
        if not booking.local_id == get_jwt_identity():
            log(f"Unauthorized to delete booking '{booking_id}'.", uuid=_uuid, level='WARNING')
            abort(401, message = f'You are not allowed to delete the booking [{booking_id}].')
        
        service_bookings = list(ServiceBookingModel.query.filter_by(booking_id=booking_id).all())
        
        try:
            deleteAndCommit(*service_bookings, booking)
            log(f"Booking '{booking_id}' deleted.", uuid=_uuid)
            return {}
        except Exception as e:
            log(f"FATAL ERROR. Error deleting booking '{booking_id}'.", uuid=_uuid, level='ERROR', error=e)
            traceback.print_exc()
            rollback()
            abort(500, message = str(e) if DEBUG else 'Could not delete the booking.')
           
@blp.route('')
class BookingSession(MethodView):
    
    @log_route
    @blp.arguments(BookingSessionParams, location='query')
    @blp.response(404, description='La reserva no existe.')
    @blp.response(400, description='No se ha proporcionado el token de sesión.')
    @blp.response(401, description='El token de sesión es inválido.')
    @blp.response(403, description='El token de sesión ha expirado.')
    @blp.response(200, BookingSchema)
    def get(self, params, _uuid = None):
        """
        Devuelve una reserva identificada por el token de sesión del cliente.
        """
        booking = getBookingBySession(params[SESSION_GET])
        
        log(f"Getting booking '{booking.id}' by session.", uuid=_uuid)
        
        if booking.status.status == DONE_STATUS:
            log(f"Booking '{booking.id}' is done.", uuid=_uuid)
            token = SessionTokenModel.query.get_or_404(decodeToken(params[SESSION_GET])['token'])
            try:
                log(f"Deleting session token '{token.id}'.", uuid=_uuid)
                deleteAndCommit(token)
            except SQLAlchemyError as e:
                log(f"Error deleting session token '{token.id}'.", uuid=_uuid, level='ERROR', error=e)
                traceback.print_exc()
                rollback()
            abort(409, message = f"The booking is '{booking.status.name}'.")       
            
        return booking 
        
    @log_route
    @blp.arguments(BookingSessionParams, location='query')
    @blp.arguments(BookingSchema)
    @blp.response(404, description='El local no existe, el servicio no existe, el trabajador no existe o la reserva no existe.')
    @blp.response(400, description='Fecha no válida o no se ha proporcionado el token de sesión.')
    @blp.response(401, description='Token de sesión inválido.')
    @blp.response(403, description='El token de sesión ha expirado.')
    @blp.response(409, description='Ya existe una reserva en ese tiempo. El trabajador no está disponible. Los servicios deben ser del mismo grupo de trabajo. El trabajador debe ser del mismo grupo de trabajo que los servicios. El local no está disponible. La fecha está en el pasado.')
    @blp.response(200, BookingSchema)
    def put(self, params, booking_data, _uuid = None):
        """
        Actualiza una reserva identificada por el token de sesión del cliente.
        """
                
        booking = getBookingBySession(params[SESSION_GET])        

        log(f"Updating booking '{booking.id}' by session.", uuid=_uuid)

        log(f"<| Last UUID Log: [{booking.uuid_log}] |>")
        booking.uuid_log = _uuid

        status = booking.status.status

        if status == CANCELLED_STATUS or status == DONE_STATUS:
            log(f"Booking '{booking.id}' is cancelled or done. Status: {status}", uuid=_uuid)
            abort(409, message = f"The booking is '{booking.status.name}'.")

        session = None

        try:
            booking, _ = createOrUpdateBooking(booking_data, booking.local_id, bookingModel=booking, _uuid=_uuid)
            log(f"Booking '{booking.id}' updated by session.", uuid=_uuid)
            log(f"Sending updated email for booking '{booking.id}'.", uuid=_uuid)
            send_updated_mail_async(booking.local_id, booking.id, _uuid=_uuid)
            return booking
        except (StatusNotFoundException, WeekdayNotFoundException) as e:
            log(f"Error updating booking '{booking.id}' by session.", uuid=_uuid, level='ERROR', error=e)
            abort(500, message = str(e))
        except LocalOverloadedException as e:
            log(f"Error updating booking '{booking.id}' by session.", uuid=_uuid, level='ERROR', error=e)
            abort(503, message = str(e))
        except ModelNotFoundException as e:
            log(f"Error updating booking '{booking.id}' by session.", uuid=_uuid, level='WARNING', error=e)
            abort(404, message = str(e))
        except ValueError as e:
            log(f"Error updating booking '{booking.id}' by session.", uuid=_uuid, level='WARNING', error=e)
            abort(400, message = str(e))
        except (PastDateException, WrongServiceWorkGroupException, LocalUnavailableException, ClosedDayException, WrongWorkerWorkGroupException, WorkerUnavailableException, AlredyBookingExceptionException) as e:
            log(f"Error updating booking '{booking.id}' by session.", uuid=_uuid, level='WARNING', error=e) 
            abort(409, message = str(e))
        except Exception as e:
            log(f"FATAL ERROR. Error updating booking '{booking.id}' by session.", uuid=_uuid, level='ERROR', error=e)
            traceback.print_exc()
            rollback(session)
            if session is not None: session.close()
            abort(500, message = str(e) if DEBUG else 'Could not create the booking.')   
            
    @log_route
    @blp.arguments(BookingSessionParams, location='query')
    @blp.arguments(BookingPatchSchema)
    @blp.response(404, description='El local no existe, el servicio no existe, el trabajador no existe o la reserva no existe.')
    @blp.response(400, description='Fecha no válida o no se ha proporcionado el token de sesión.')
    @blp.response(401, description='Token de sesión inválido.')
    @blp.response(403, description='El token de sesión ha expirado.')
    @blp.response(409, description='Ya existe una reserva en ese tiempo. El trabajador no está disponible. Los servicios deben ser del mismo grupo de trabajo. El trabajador debe ser del mismo grupo de trabajo que los servicios. El local no está disponible. La fecha está en el pasado.')
    @blp.response(200, BookingSchema)
    def patch(self, params, booking_data, _uuid = None):
        """
        Actualiza una reserva identificada por el token de sesión del cliente indicando los campos a modificar.
        """
                
        booking = getBookingBySession(params[SESSION_GET])        

        log(f"Updating booking '{booking.id}' by session.", uuid=_uuid)
        
        log(f"<| Last UUID Log: [{booking.uuid_log}] |>")
        booking.uuid_log = _uuid
        
        status = booking.status.status

        if status == CANCELLED_STATUS or status == DONE_STATUS:
            log(f"Booking '{booking.id}' is cancelled or done. Status: {status}", uuid=_uuid)
            abort(409, message = f"The booking is '{booking.status.name}'.")
                
        booking_data = patchBooking(booking, booking_data)

        session = None

        try:
            booking, _ = createOrUpdateBooking(booking_data, booking.local_id, bookingModel=booking, _uuid=_uuid)
            log(f"Booking '{booking.id}' updated by session.", uuid=_uuid)
            return booking
        except (StatusNotFoundException, WeekdayNotFoundException) as e:
            log(f"Error updating booking '{booking.id}' by session.", uuid=_uuid, level='ERROR', error=e)
            abort(500, message = str(e))
        except LocalOverloadedException as e:
            log(f"Error updating booking '{booking.id}' by session.", uuid=_uuid, level='ERROR', error=e)
            abort(503, message = str(e))
        except ModelNotFoundException as e:
            log(f"Error updating booking '{booking.id}' by session.", uuid=_uuid, level='WARNING', error=e)
            abort(404, message = str(e))
        except ValueError as e:
            log(f"Error updating booking '{booking.id}' by session.", uuid=_uuid, level='WARNING', error=e)
            abort(400, message = str(e))
        except (PastDateException, WrongServiceWorkGroupException, LocalUnavailableException, ClosedDayException, WrongWorkerWorkGroupException, WorkerUnavailableException, AlredyBookingExceptionException) as e:
            log(f"Error updating booking '{booking.id}' by session.", uuid=_uuid, level='WARNING', error=e)
            abort(409, message = str(e))
        except Exception as e:
            log(f"FATAL ERROR. Error updating booking '{booking.id}' by session.", uuid=_uuid, level='ERROR', error=e)
            traceback.print_exc()
            rollback(session)
            if session is not None: session.close()
            abort(500, message = str(e) if DEBUG else 'Could not create the booking.')   
    
    @log_route
    @blp.arguments(BookingSessionParams, location='query')
    @blp.arguments(CommentSchema)
    @blp.response(404, description='La reserva no existe.')
    @blp.response(400, description='No se ha proporcionado el token de sesión.')
    @blp.response(401, description='El token de sesión es inválido.')
    @blp.response(403, description='El token de sesión ha expirado.')
    @blp.response(204, description='La reserva ha sido cancelada.')
    def delete(self, params, data, _uuid = None):
        """
        Cancela una reserva identificada por el token de sesión del cliente.
        """
        booking = getBookingBySession(params[SESSION_GET])
        
        log(f"Deleting booking '{booking.id}' by session.", uuid=_uuid)
        
        log(f"<| Last UUID Log: [{booking.uuid_log}] |>")
        booking.uuid_log = _uuid
        
        status = booking.status.status
        
        if status == DONE_STATUS or status == CANCELLED_STATUS:
            log(f"Booking '{booking.id}' is done or cancelled. Status: {status}", uuid=_uuid) 
            abort(409, message = f"The booking is '{booking.status.name}'.")
        
        comment = None
        
        if 'comment' in data:
            comment = data['comment']
        
        try:
            cancelBooking(booking, comment=comment) #TODO: Add comment?
            log(f"Booking '{booking.id}' cancelled by session.", uuid=_uuid) 
            log(f"Sending cancelled email for booking '{booking.id}'.", uuid=_uuid)
            send_cancelled_mail_async(booking.local_id, booking.id, _uuid=_uuid)
            return {}
        except SQLAlchemyError as e:
            log(f"Error cancelling booking '{booking.id}' by session.", uuid=_uuid, level='ERROR', error=e)
            traceback.print_exc()
            abort(500, message = str(e) if DEBUG else 'Could not delete the booking.')
                
    @log_route
    @blp.arguments(UpdateParams, location='query')
    @blp.arguments(BookingSchema)
    @blp.response(404, description='El local no existe, el servicio no existe, el trabajador no existe o la reserva no existe.')
    @blp.response(400, description='Fecha no válida o no se ha proporcionado el token de sesión.')
    @blp.response(401, description='No tienes permisos para crear la reserva.')
    @blp.response(409, description='Ya existe una reserva en ese tiempo. El trabajador no está disponible. Los servicios deben ser del mismo grupo de trabajo. El trabajador debe ser del mismo grupo de trabajo que los servicios. El local no está disponible. La fecha está en el pasado.')
    @blp.response(201, BookingSchema)
    @jwt_required(refresh=True)
    def post(self, params, new_booking, _uuid = None):
        """
        Crea una nueva reserva identificada por parte del local, identificado por el token de sesión refresco.
        """
                
        force = 'force' in params and params['force']
        notify = 'notify' in params and params['notify']
        
        session = None
        
        try:
            
            local_id = get_jwt_identity()
            
            log(f"Creating a new booking by local. Local: '{local_id}'.", uuid=_uuid)
            
            log(f"<| Last UUID Log: [NULL] |>")
            
            new_booking['status'] = CONFIRMED_STATUS
            
            booking, unregisterFromCache = createOrUpdateBooking(new_booking, local_id, commit=False, force=force, _uuid = _uuid)
            
            booking.uuid_log = _uuid
            
            log(f"Booking created by local. Local: '{local_id}'.", uuid=_uuid)
            
            try:            
                commit(session)
            except SQLAlchemyError as e:
                log(f"Error commiting booking by local. Local: '{local_id}'. Unregistering from cache", uuid=_uuid, level='ERROR', error=e)
                log("Unregistering from cache.", uuid=_uuid)
                unregisterFromCache()
                raise e
            
            log("Unregistering from cache.", uuid=_uuid)
            unregisterFromCache()
            
            if notify:
                log(f"Sending confirmation email for booking '{booking.id}'.", uuid=_uuid)
                send_confirmed_mail_async(booking.local_id, booking.id, _uuid = _uuid)
            
            return booking
        
        except (StatusNotFoundException, WeekdayNotFoundException) as e:
            log(f"Error creating booking by local. Local: '{local_id}'.", uuid=_uuid, level='ERROR', error=e)
            abort(500, message = str(e))
        except LocalOverloadedException as e:
            log(f"Error creating booking by local. Local: '{local_id}'.", uuid=_uuid, level='ERROR', error=e)
            abort(503, message = str(e))
        except (ModelNotFoundException, LocalNotFoundException) as e:
            log(f"Error creating booking by local. Local: '{local_id}'.", uuid=_uuid, level='WARNING', error=e)
            abort(404, message = str(e))
        except ValueError as e:
            log(f"Error creating booking by local. Local: '{local_id}'.", uuid=_uuid, level='WARNING', error=e)
            abort(400, message = str(e))
        except (PastDateException, WrongServiceWorkGroupException, LocalUnavailableException, ClosedDayException, WrongWorkerWorkGroupException, WorkerUnavailableException, AlredyBookingExceptionException) as e:
            log(f"Error creating booking by local. Local: '{local_id}'.", uuid=_uuid, level='WARNING', error=e)
            abort(409, message = str(e))
        except Exception as e:
            log(f"FATAL ERROR. Error creating booking by local. Local: '{local_id}'.", uuid=_uuid, level='ERROR', error=e)
            traceback.print_exc()
            rollback(session)
            if session is not None: session.close()
            abort(500, message = str(e) if DEBUG else 'Could not create the booking.')
        
@blp.route('confirm')
class BookingConfirm(MethodView):
    
    @log_route
    @blp.arguments(BookingSessionParams, location='query')
    @blp.response(404, description='La reserva no existe.')
    @blp.response(400, description='No se ha proporcionado el token de sesión.')
    @blp.response(401, description='El token de sesión es inválido.')
    @blp.response(403, description='El token de sesión ha expirado.')
    @blp.response(409, description='La reserva no está pendiente.')
    @blp.response(200, BookingSchema)
    def get(self, params, _uuid = None):
        """
        Confirma una reserva identificado por el token de sesión del cliente. Cambia el estado a confirmado.
        """
        booking = getBookingBySession(params[SESSION_GET])
        
        log(f"Confirming booking '{booking.id}' by session.", uuid=_uuid)
        
        log(f"<| Last UUID Log: [{booking.uuid_log}] |>")
        booking.uuid_log = _uuid
        
        if not booking.status.status == PENDING_STATUS:
            log(f"Booking '{booking.id}' is not pending. Status: {booking.status.status}", uuid=_uuid)
            status = StatusModel.query.get(booking.status_id)
            if not status: abort(500, message='The status was not found.')
            abort(409, message=f"The booking is '{status.name}'.")
        
        try:
            booking = confirmBooking(booking)
        except (SQLAlchemyError, StatusNotFoundException) as e:
            log(f"Error confirming booking '{booking.id}' by session.", uuid=_uuid, level='ERROR', error=e)
            traceback.print_exc()
            rollback()
            abort(500, message = str(e) if DEBUG else 'Could not confirm the booking.')
            
        log(f"Sending confirmation email for booking '{booking.id}'.", uuid=_uuid)
        send_confirmed_mail_async(booking.local_id, booking.id, _uuid = _uuid)
            
        return booking
    
@blp.route('confirm/<int:booking_id>')
class BookingConfirmId(MethodView):
    
    @log_route
    @blp.arguments(NotifyParams, location='query')
    @blp.response(404, description='La reserva no existe.')
    @blp.response(401, description='No tienes permisos para confirmar la reserva.')
    @blp.response(200, BookingSchema)
    @jwt_required(refresh=True)
    def get(self, params, booking_id, _uuid = None):
        """
        Confirma una reserva por parte del local identificado por el token de refresco. Cambia el estado a confirmado.
        """
        
        booking = BookingModel.query.get_or_404(booking_id)
        
        log(f"Confirming booking '{booking.id}' by local.", uuid=_uuid)
        
        log(f"<| Last UUID Log: [{booking.uuid_log}] |>")
        booking.uuid_log = _uuid
        
        local = LocalModel.query.get(get_jwt_identity())
        
        notify = 'notify' in params and params['notify']
        
        if not booking.local_id == local.id:
            log(f"Unauthorized to confirm booking '{booking.id}'.", uuid=_uuid, level='WARNING')
            abort(401, message = f'You are not allowed to confirm the booking [{booking.id}].')
        
        if not booking.status.status == PENDING_STATUS:
            log(f"Booking '{booking.id}' is not pending. Status: {booking.status.status}", uuid=_uuid)
            status = StatusModel.query.get(booking.status_id)
            if not status: abort(500, message='The status was not found.')
            abort(409, message=f"The booking is '{status.name}'.")
        
        try:
            booking = confirmBooking(booking)
        except SQLAlchemyError as e:
            log(f"Error confirming booking '{booking.id}'.", uuid=_uuid, level='ERROR', error=e)
            traceback.print_exc()
            rollback()
            abort(500, message = str(e) if DEBUG else 'Could not confirm the booking.')
            
        
        if notify:
            log(f"Sending confirmation email for booking '{booking.id}'.", uuid=_uuid)
            send_confirmed_mail_async(booking.local_id, booking.id, _uuid = _uuid)
            
        return booking
 
@blp.route('cancel/<int:booking_id>')
class BookingCancelId(MethodView):
    
    @log_route
    @blp.arguments(NotifyParams, location='query')
    @blp.arguments(CommentSchema)
    @blp.response(404, description='La reserva no existe.')
    @blp.response(401, description='No tienes permisos para cancelar la reserva.')
    @blp.response(204, BookingSchema)
    @jwt_required(refresh=True)
    def delete(self, params, data, booking_id, _uuid = None):
        """
        Cancela una reserva por parte del local identificado por el token de refresco. Cambia el estado a cancelado.
        """
        booking = BookingModel.query.get_or_404(booking_id)
        
        log(f"Cancelling booking '{booking.id}' by local.", uuid=_uuid)
        
        log(f"<| Last UUID Log: [{booking.uuid_log}] |>")
        booking.uuid_log = _uuid
        
        local = LocalModel.query.get(get_jwt_identity())
        
        notify = 'notify' in params and params['notify']
        
        if not booking.local_id == local.id:
            log(f"Unauthorized to cancel booking '{booking.id}'.", uuid=_uuid, level='WARNING')
            abort(401, message = f'You are not allowed to cancel the booking [{booking.id}].')
        
        if booking.status.status == DONE_STATUS or booking.status.status == CANCELLED_STATUS:
            log(f"Booking '{booking.id}' is done or cancelled. Status: {booking.status.status}", uuid=_uuid)
            abort(409, message = f"The booking is '{booking.status.name}'.")
        
        comment = None
        
        if 'comment' in data:
            comment = data['comment']
        
        try:
            cancelBooking(booking, comment=comment) #TODO comment?
            
            if notify:
                log(f"Sending cancelled email for booking '{booking.id}'.", uuid=_uuid)
                send_cancelled_mail_async(booking.local_id, booking.id)
            
            return {}
        except SQLAlchemyError as e:
            log(f"Error cancelling booking '{booking.id}'.", uuid=_uuid, level='ERROR', error=e)
            traceback.print_exc()
            abort(500, message = str(e) if DEBUG else 'Could not delete the booking.')
    
@blp.route('status')
class Status(MethodView):
    
    @blp.response(200, StatusSchema(many=True))
    def get(self):
        """
        Devuelve los estados posibles de las reservas.
        """        
        return StatusModel.query.all()
    
    
@blp.route('admin')
class BookingAdmin(MethodView):
    
    @log_route
    @blp.arguments(BookingSchema)
    @blp.response(404, description='El token de administrador no existe.')
    @blp.response(403, description='No tienes permisos para usar este endpoint.')
    @blp.response(401, description='Falta la cabecera de autorización.')
    @blp.response(201, NewBookingSchema)
    def post(self, booking_data, _uuid = None):
        """
        [ADMIN PRIVATE] Crear una nueva reserva por parte del administrador del sistema.
        """
        log(f"Creating a new booking by admin.", uuid=_uuid)
        token_header = request.headers.get('Authorization')

        if not token_header or not token_header.startswith('Bearer '):
            log(f"Missing Authorization Header.", uuid=_uuid, level='WARNING')
            return abort(401, message='Missing Authorization Header')
        
        token = token_header.split(' ', 1)[1]
        
        identity = decodeJWT(token)['sub']
        id = decodeJWT(token)['token']
                
        token = SessionTokenModel.query.get_or_404(id)
        
        if identity != ADMIN_IDENTITY or token.user_session.user != ADMIN_ROLE:
            log(f"Unauthorized to use this endpoint.", uuid=_uuid, level='WARNING')
            abort(403, message = 'You are not allowed to use this endpoint.')
            
        services_ids = booking_data.pop('services_ids')
        services = [ServiceModel.query.get_or_404(id) for id in services_ids]

        if 'worker_id' not in booking_data:
            log(f"Missing worker_id.", uuid=_uuid, level='WARNING')
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
            
            log(f"Booking '{booking.id}' created by admin.", uuid=_uuid)
            
            return {
                "booking": booking,
                "timeout": timeout,
                "session_token": token
            }
        except SQLAlchemyError as e:
            log(f"Error creating booking by admin.", uuid=_uuid, level='ERROR', error=e)
            traceback.print_exc()
            rollback()
            abort(500, message = str(e) if DEBUG else 'Could not create the booking.')
        
        
        
        