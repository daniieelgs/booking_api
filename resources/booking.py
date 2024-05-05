from datetime import datetime, timedelta
from flask import request
from flask.views import MethodView
from flask_smorest import Blueprint, abort
from jwt import ExpiredSignatureError
from helpers.BookingController import calculatEndTimeBooking, calculateExpireBookingToken, cancelBooking, confirmBooking, createOrUpdateBooking, deserializeBooking, getBookings, getBookingBySession as getBookingBySessionHelper
from helpers.BookingEmailController import send_cancelled_mail_async, send_confirmed_mail_async, send_updated_mail_async, start_waiter_booking_status
from helpers.DataController import getDataRequest, getMonthDataRequest, getWeekDataRequest
from helpers.DatetimeHelper import now
from helpers.EmailController import send_confirm_booking_mail
from helpers.error.BookingError.AlredyBookingException import AlredyBookingExceptionException
from helpers.error.BookingError.BookingNotFoundError import BookingNotFoundException
from helpers.error.BookingError.LocalUnavailableException import LocalUnavailableException
from helpers.error.DataError.PastDateException import PastDateException
from helpers.error.BookingError.WorkerUnavailable import WorkerUnavailableException
from helpers.error.BookingError.WrongServiceWorkGroupException import WrongServiceWorkGroupException
from helpers.error.BookingError.WrongWorkerWorkGroupException import WrongWorkerWorkGroupException
from helpers.error.DataError.UnspecifedDateException import UnspecifedDateException
from helpers.error.LocalError.LocalNotFoundException import LocalNotFoundException
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

from globals import ADMIN_IDENTITY, ADMIN_ROLE, CANCELLED_STATUS, DEBUG, CONFIRMED_STATUS, DONE_STATUS, PENDING_STATUS, SESSION_GET, STATUS_LIST_GET, USER_ROLE, WEEK_DAYS, WORK_GROUP_ID_GET, WORKER_ID_GET
from models.local import LocalModel
from models.service import ServiceModel
from models.service_booking import ServiceBookingModel
from models.session_token import SessionTokenModel
from models.status import StatusModel
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
    
    @blp.arguments(BookingParams, location='query')
    @blp.response(404, description='El local no existe.')
    @blp.response(422, description='Fecha no especificada.')
    @blp.response(204, description='El local no tiene reservas para la fecha indicada.')
    @blp.response(200, PublicBookingListSchema)
    def get(self, _, local_id):
        """
        Devuelve las reservas públicas de una fecha específica.
        """      
        
        try:
            datetime_init, datetime_end = getDataRequest(request)
            
            worker_id = request.args.get(WORKER_ID_GET, None)
            work_group_id = request.args.get(WORK_GROUP_ID_GET, None)
            
            bookings = getBookings(local_id, datetime_init, datetime_end, status=[CONFIRMED_STATUS, PENDING_STATUS], worker_id=worker_id, work_group_id=work_group_id)        
        except ValueError as e:
            abort(400, message=str(e))
        except LocalNotFoundException as e:
            abort(404, message=str(e))
        except UnspecifedDateException as e:
            abort(422, message=str(e))    
                
        return {"bookings": bookings, "total": len(bookings)}
    
@blp.route('/local/<string:local_id>/week')
class SeePublicBookingWeek(MethodView):
    
    @blp.arguments(BookingWeekParams, location='query')
    @blp.response(404, description='El local no existe.')
    @blp.response(422, description='Fecha no especificada.')
    @blp.response(204, description='El local no tiene reservas para la fecha indicada.')
    @blp.response(200, PublicBookingListSchema)
    def get(self, _, local_id):
        """
        Devuelve las reservas públicas de una semana.
        """
        
        try:
            datetime_init, datetime_end = getWeekDataRequest(request)
                
            worker_id = request.args.get(WORKER_ID_GET, None)
            work_group_id = request.args.get('work_group_id', None)
                
            bookings = getBookings(local_id, datetime_init, datetime_end, status=[CONFIRMED_STATUS, PENDING_STATUS], worker_id=worker_id, work_group_id=work_group_id)
        except ValueError as e:
            abort(400, message=str(e))
        except LocalNotFoundException as e:
            abort(404, message=str(e))
        except UnspecifedDateException as e:
            abort(422, message=str(e))    
                  
        return {"bookings": bookings, "total": len(bookings)} 
    
@blp.route('/local/<string:local_id>/month')
class SeePublicBookingMonth(MethodView):
    
    @blp.arguments(BookingWeekParams, location='query')
    @blp.response(404, description='El local no existe.')
    @blp.response(422, description='Fecha no especificada.')
    @blp.response(204, description='El local no tiene reservas para la fecha indicada.')
    @blp.response(200, PublicBookingListSchema)
    def get(self, _, local_id):
        """
        Devuelve las reservas públicas de un mes.
        """
        
        try:
            datetime_init, datetime_end = getMonthDataRequest(request)
            
            worker_id = request.args.get(WORKER_ID_GET, None)
            work_group_id = request.args.get('work_group_id', None)
                
            bookings = getBookings(local_id, datetime_init, datetime_end, status=[CONFIRMED_STATUS, PENDING_STATUS], worker_id=worker_id, work_group_id=work_group_id)
            
        except ValueError as e:
            abort(400, message=str(e))
        except LocalNotFoundException as e:
            abort(404, message=str(e))
        except UnspecifedDateException as e:
            abort(422, message=str(e))    
            
        
                
        return {"bookings": bookings, "total": len(bookings)}  
    
@blp.route('/all')
class SeeBookingWeek(MethodView):
    
    @blp.arguments(BookingAdminParams, location='query')
    @blp.response(404, description='El local no existe.')
    @blp.response(422, description='Fecha no especificada.')
    @blp.response(204, description='El local no tiene reservas para la fecha indicada.')
    @blp.response(200, BookingAdminListSchema)
    @jwt_required(refresh=True)
    def get(self, _):
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
            
            bookings = getBookings(get_jwt_identity(), datetime_init, datetime_end, status=status, worker_id=worker_id, work_group_id=work_group_id, client_filter=client_filter)
            
        except ValueError as e:
            abort(400, message=str(e))
        except LocalNotFoundException as e:
            abort(404, message=str(e))
        except UnspecifedDateException as e:
            abort(422, message=str(e))     
                                
        return {"bookings": bookings, "total": len(bookings)}  
       
@blp.route('/all/week')
class SeeBookingWeek(MethodView):
    
    @blp.arguments(BookingAdminWeekParams, location='query')
    @blp.response(404, description='El local no existe.')
    @blp.response(422, description='Fecha no especificada.')
    @blp.response(204, description='El local no tiene reservas para la fecha indicada.')
    @blp.response(200, BookingAdminListSchema)
    @jwt_required(refresh=True)
    def get(self, _):
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
                
            bookings = getBookings(get_jwt_identity(), datetime_init, datetime_end, status=status, worker_id=worker_id, work_group_id=work_group_id, client_filter=client_filter)
            
        except ValueError as e:
            abort(400, message=str(e))
        except LocalNotFoundException as e:
            abort(404, message=str(e))
        except UnspecifedDateException as e:
            abort(422, message=str(e))    
                                                
        return {"bookings": bookings, "total": len(bookings)}  
    
@blp.route('/all/month')
class SeeBookingMonth(MethodView):
    
    @blp.arguments(BookingAdminWeekParams, location='query')
    @blp.response(404, description='El local no existe.')
    @blp.response(422, description='Fecha no especificada.')
    @blp.response(204, description='El local no tiene reservas para la fecha indicada.')
    @blp.response(200, BookingAdminListSchema)
    @jwt_required(refresh=True)
    def get(self, _):
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
                
            bookings = getBookings(get_jwt_identity(), datetime_init, datetime_end, status=status, worker_id=worker_id, work_group_id=work_group_id, client_filter=client_filter)
            
        except ValueError as e:
            abort(400, message=str(e))
        except LocalNotFoundException as e:
            abort(404, message=str(e))
        except UnspecifedDateException as e:
            abort(422, message=str(e))    
        
        return {"bookings": bookings, "total": len(bookings)}  

@blp.route('/local/<string:local_id>')
class Booking(MethodView):
    
    @blp.arguments(BookingSchema)
    @blp.response(404, description='El local no existe, el servicio no existe o el trabajador no existe.')
    @blp.response(400, description='Formato de fecha no válido o no se ha proporcionado el token de sesión.')
    @blp.response(409, description='Ya existe una reserva en ese tiempo. El trabajador no está disponible. Los servicios deben ser del mismo grupo de trabajo. El trabajador debe ser del mismo grupo de trabajo que los servicios. El local no está disponible. La fecha está en el pasado.')
    @blp.response(201, NewBookingSchema)
    def post(self, new_booking, local_id):
        """
        Crea una nueva reserva.
        """
                
        local = LocalModel.query.get_or_404(local_id)
        
        session = None
        
        try:
            
            booking, session = createOrUpdateBooking(new_booking, local=local, commit=False)
                        
            exp:timedelta = calculateExpireBookingToken(booking.datetime_init, local.location)
                        
            token = generateTokens(booking.id, booking.local_id, refresh_token=True, expire_refresh=exp, user_role=USER_ROLE)
                        
            booking.email_confirm = True
                        
            commit(session)
                        
            email_confirm = send_confirm_booking_mail(local, booking, token)
                        
            timeout = None
            
            if email_confirm:
                timeout_local = local.local_settings.booking_timeout
                timeout = start_waiter_booking_status(booking.id, timeout=timeout_local)
            else:
                booking.email_confirm = False
                    
                confirmBooking(booking, session=session)
                    
                send_confirmed_mail_async(local_id, booking.id)
                    
                addAndCommit(booking, session)
              
            if session is not None: session.close()
                    
            return {
                "booking": booking,
                "timeout": timeout,
                "email_confirm": email_confirm,
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
            rollback(session)
            if session is not None: session.close()
            abort(500, message = str(e) if DEBUG else 'Could not create the booking.')   
             

@blp.route('/<int:booking_id>')
class BookingAdmin(MethodView):
    
    @blp.response(404, description='La reserva no existe.')
    @blp.response(401, description='No tienes permisos para obtener la reserva.')
    @blp.response(200, BookingAdminSchema)
    @jwt_required(refresh=True)
    def get(self, booking_id):
        """
        Devuelve una reserva. Identificado por el local.
        """
        
        booking = BookingModel.query.get_or_404(booking_id)
        
        if not booking.local_id == get_jwt_identity():
            abort(401, message = f'You are not allowed to get the booking [{booking_id}].')
                
        return booking
    
    
    @blp.arguments(UpdateParams, location='query')
    @blp.arguments(BookingAdminSchema)
    @blp.response(404, description='El local no existe, el servicio no existe, el trabajador no existe o la reserva no existe.')
    @blp.response(400, description='Fecha no válida.')
    @blp.response(401, description='No tienes permisos para actualizar la reserva.')
    @blp.response(409, description='Ya existe una reserva en ese tiempo. El trabajador no está disponible. Los servicios deben ser del mismo grupo de trabajo. El trabajador debe ser del mismo grupo de trabajo que los servicios. El local no está disponible. La fecha está en el pasado.')
    @blp.response(200, BookingSchema)
    @jwt_required(refresh=True)
    def put(self, params, booking_data, booking_id):
        """
        Actualiza una reserva. Por parte del local.
        """
        
        booking = BookingModel.query.get(booking_id)
        
        force = 'force' in params and params['force']
        notify = 'notify' in params and params['notify']
        
        if not booking:
            abort(404, message = f'The booking [{booking_id}] was not found.')
                
        if booking.local_id != get_jwt_identity():
            abort(401, message = f'You are not allowed to update the booking [{booking_id}].')
            
        booking_data['status'] = booking_data.pop('new_status')
            
        session = None
                
        try:
            booking, session = createOrUpdateBooking(booking_data, booking.local_id, bookingModel=booking, force=force)
            
            if notify: send_updated_mail_async(booking.local_id, booking.id)
            
            return booking
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
            rollback(session)
            if session is not None: session.close()
            abort(500, message = str(e) if DEBUG else 'Could not create the booking.')
    
    @blp.arguments(UpdateParams, location='query')
    @blp.arguments(BookingAdminPatchSchema)
    @blp.response(404, description='El local no existe, el servicio no existe, el trabajador no existe o la reserva no existe.')
    @blp.response(400, description='Fecha no válida.')
    @blp.response(401, description='No tienes permisos para actualizar la reserva.')
    @blp.response(409, description='Ya existe una reserva en ese tiempo. El trabajador no está disponible. Los servicios deben ser del mismo grupo de trabajo. El trabajador debe ser del mismo grupo de trabajo que los servicios. El local no está disponible. La fecha está en el pasado.')
    @blp.response(200, BookingSchema)
    @jwt_required(refresh=True)
    def patch(self, params, booking_data, booking_id):
        """
        Actualiza una reserva indicando los campos a modificar. Por parte del local.
        """
        
        notify = 'notify' in params and params['notify']
        force = 'force' in params and params['force']
        
        booking = BookingModel.query.get(booking_id)

        if not booking:
            abort(404, message = f'The booking [{booking_id}] was not found.')
                
        if booking.local_id != get_jwt_identity():
            abort(401, message = f'You are not allowed to update the booking [{booking_id}].')
            
        if 'new_status' in booking_data: booking_data['status'] = booking_data.pop('new_status')
                
        booking_data = patchBooking(booking, booking_data, admin = True)
              
        session = None
                
        try:
            booking, session = createOrUpdateBooking(booking_data, booking.local_id, bookingModel=booking, force=force)
            
            if notify: send_updated_mail_async(booking.local_id, booking.id)
            
            return booking
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
            rollback(session)
            if session is not None: session.close()
            abort(500, message = str(e) if DEBUG else 'Could not create the booking.')  
    
    @blp.response(404, description='La reserva no existe.')
    @blp.response(401, description='No tienes permisos para eliminar la reserva.')
    @blp.response(204, description='La reserva ha sido eliminada.')
    @jwt_required(refresh=True)
    def delete(self, booking_id):
        """
        Elimina una reserva. WARNING: No se recomienda ya que, no se puede deshacer. Si se desea cancelar una reserva, se recomienda cambiar el estado de la reserva o bien utilizar el endpoint para cancelar una reserva [cancel/{booking_id}].
        """
        
        booking = BookingModel.query.get_or_404(booking_id)
        
        if not booking.local_id == get_jwt_identity():
            abort(401, message = f'You are not allowed to delete the booking [{booking_id}].')
        
        service_bookings = list(ServiceBookingModel.query.filter_by(booking_id=booking_id).all())
        
        try:
            deleteAndCommit(*service_bookings, booking)
            return {}
        except Exception as e:
            traceback.print_exc()
            rollback()
            abort(500, message = str(e) if DEBUG else 'Could not delete the booking.')
           
@blp.route('')
class BookingSession(MethodView):
    
    @blp.arguments(BookingSessionParams, location='query')
    @blp.response(404, description='La reserva no existe.')
    @blp.response(400, description='No se ha proporcionado el token de sesión.')
    @blp.response(401, description='El token de sesión es inválido.')
    @blp.response(403, description='El token de sesión ha expirado.')
    @blp.response(200, BookingSchema)
    def get(self, params):
        """
        Devuelve una reserva identificada por el token de sesión del cliente.
        """
        booking = getBookingBySession(params[SESSION_GET])
        
        if booking.status.status == DONE_STATUS:
            token = SessionTokenModel.query.get_or_404(decodeToken(params[SESSION_GET])['token'])
            try:
                deleteAndCommit(token)
            except SQLAlchemyError:
                traceback.print_exc()
                rollback()
            abort(409, message = f"The booking is '{booking.status.name}'.")       
            
        return booking 
        
    @blp.arguments(BookingSessionParams, location='query')
    @blp.arguments(BookingSchema)
    @blp.response(404, description='El local no existe, el servicio no existe, el trabajador no existe o la reserva no existe.')
    @blp.response(400, description='Fecha no válida o no se ha proporcionado el token de sesión.')
    @blp.response(401, description='Token de sesión inválido.')
    @blp.response(403, description='El token de sesión ha expirado.')
    @blp.response(409, description='Ya existe una reserva en ese tiempo. El trabajador no está disponible. Los servicios deben ser del mismo grupo de trabajo. El trabajador debe ser del mismo grupo de trabajo que los servicios. El local no está disponible. La fecha está en el pasado.')
    @blp.response(200, BookingSchema)
    def put(self, params, booking_data):
        """
        Actualiza una reserva identificada por el token de sesión del cliente.
        """
                
        booking = getBookingBySession(params[SESSION_GET])        

        if booking.status.status == CANCELLED_STATUS or booking.status.status == DONE_STATUS:
            abort(409, message = f"The booking is '{booking.status.name}'.")

        session = None

        try:
            booking, session = createOrUpdateBooking(booking_data, booking.local_id, bookingModel=booking)
            send_updated_mail_async(booking.local_id, booking.id)
            return booking
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
            rollback(session)
            if session is not None: session.close()
            abort(500, message = str(e) if DEBUG else 'Could not create the booking.')   
            
    @blp.arguments(BookingSessionParams, location='query')
    @blp.arguments(BookingPatchSchema)
    @blp.response(404, description='El local no existe, el servicio no existe, el trabajador no existe o la reserva no existe.')
    @blp.response(400, description='Fecha no válida o no se ha proporcionado el token de sesión.')
    @blp.response(401, description='Token de sesión inválido.')
    @blp.response(403, description='El token de sesión ha expirado.')
    @blp.response(409, description='Ya existe una reserva en ese tiempo. El trabajador no está disponible. Los servicios deben ser del mismo grupo de trabajo. El trabajador debe ser del mismo grupo de trabajo que los servicios. El local no está disponible. La fecha está en el pasado.')
    @blp.response(200, BookingSchema)
    def patch(self, params, booking_data):
        """
        Actualiza una reserva identificada por el token de sesión del cliente indicando los campos a modificar.
        """
                
        booking = getBookingBySession(params[SESSION_GET])        

        if booking.status.status == CANCELLED_STATUS or booking.status.status == DONE_STATUS:
            abort(409, message = f"The booking is '{booking.status.name}'.")
                
        booking_data = patchBooking(booking, booking_data)

        session = None

        try:
            booking, session = createOrUpdateBooking(booking_data, booking.local_id, bookingModel=booking)
            return booking
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
            rollback(session)
            if session is not None: session.close()
            abort(500, message = str(e) if DEBUG else 'Could not create the booking.')   
    
    @blp.arguments(BookingSessionParams, location='query')
    @blp.arguments(CommentSchema)
    @blp.response(404, description='La reserva no existe.')
    @blp.response(400, description='No se ha proporcionado el token de sesión.')
    @blp.response(401, description='El token de sesión es inválido.')
    @blp.response(403, description='El token de sesión ha expirado.')
    @blp.response(204, description='La reserva ha sido cancelada.')
    def delete(self, params, data):
        """
        Cancela una reserva identificada por el token de sesión del cliente.
        """
        booking = getBookingBySession(params[SESSION_GET])
        
        if booking.status.status == DONE_STATUS or booking.status.status == CANCELLED_STATUS:
            abort(409, message = f"The booking is '{booking.status.name}'.")
        
        comment = None
        
        if 'comment' in data:
            comment = data['comment']
        
        try:
            cancelBooking(booking, comment=comment)
            send_cancelled_mail_async(booking.local_id, booking.id)
            return {}
        except SQLAlchemyError as e:
            traceback.print_exc()
            abort(500, message = str(e) if DEBUG else 'Could not delete the booking.')
                
    @blp.arguments(UpdateParams, location='query')
    @blp.arguments(BookingSchema)
    @blp.response(404, description='El local no existe, el servicio no existe, el trabajador no existe o la reserva no existe.')
    @blp.response(400, description='Fecha no válida o no se ha proporcionado el token de sesión.')
    @blp.response(401, description='No tienes permisos para crear la reserva.')
    @blp.response(409, description='Ya existe una reserva en ese tiempo. El trabajador no está disponible. Los servicios deben ser del mismo grupo de trabajo. El trabajador debe ser del mismo grupo de trabajo que los servicios. El local no está disponible. La fecha está en el pasado.')
    @blp.response(201, BookingSchema)
    @jwt_required(refresh=True)
    def post(self, params, new_booking):
        """
        Crea una nueva reserva identificada por parte del local, identificado por el token de sesión refresco.
        """
        
        force = 'force' in params and params['force']
        notify = 'notify' in params and params['notify']
        
        session = None
        
        try:
            
            local_id = get_jwt_identity()
            
            new_booking['status'] = CONFIRMED_STATUS
            
            booking, session = createOrUpdateBooking(new_booking, local_id, commit=False, force=force)
            
            commit(session)
            
            if notify:
                send_confirmed_mail_async(booking.local_id, booking.id)
            
            return booking
        
        except (StatusNotFoundException, WeekdayNotFoundException) as e:
            abort(500, message = str(e))
        except (ModelNotFoundException, LocalNotFoundException) as e:
            abort(404, message = str(e))
        except ValueError as e:
            abort(400, message = str(e))
        except (PastDateException, WrongServiceWorkGroupException, LocalUnavailableException, WrongWorkerWorkGroupException, WorkerUnavailableException, AlredyBookingExceptionException) as e:
            abort(409, message = str(e))
        except Exception as e:
            traceback.print_exc()
            rollback(session)
            if session is not None: session.close()
            abort(500, message = str(e) if DEBUG else 'Could not create the booking.')
        
@blp.route('confirm')
class BookingConfirm(MethodView):
    
    @blp.arguments(BookingSessionParams, location='query')
    @blp.response(404, description='La reserva no existe.')
    @blp.response(400, description='No se ha proporcionado el token de sesión.')
    @blp.response(401, description='El token de sesión es inválido.')
    @blp.response(403, description='El token de sesión ha expirado.')
    @blp.response(409, description='La reserva no está pendiente.')
    @blp.response(200, BookingSchema)
    def get(self, params):
        """
        Confirma una reserva identificado por el token de sesión del cliente. Cambia el estado a confirmado.
        """
        booking = getBookingBySession(params[SESSION_GET])
        
        if not booking.status.status == PENDING_STATUS:
            status = StatusModel.query.get(booking.status_id)
            if not status: abort(500, message='The status was not found.')
            abort(409, message=f"The booking is '{status.name}'.")
        
        try:
            booking = confirmBooking(booking)
        except (SQLAlchemyError, StatusNotFoundException) as e:
            traceback.print_exc()
            rollback()
            abort(500, message = str(e) if DEBUG else 'Could not confirm the booking.')
            
        send_confirmed_mail_async(booking.local_id, booking.id)
            
        return booking
    
@blp.route('confirm/<int:booking_id>')
class BookingConfirmId(MethodView):
    
    @blp.arguments(NotifyParams, location='query')
    @blp.response(404, description='La reserva no existe.')
    @blp.response(401, description='No tienes permisos para confirmar la reserva.')
    @blp.response(200, BookingSchema)
    @jwt_required(refresh=True)
    def get(self, params, booking_id):
        """
        Confirma una reserva por parte del local identificado por el token de refresco. Cambia el estado a confirmado.
        """
        
        booking = BookingModel.query.get_or_404(booking_id)
        
        local = LocalModel.query.get(get_jwt_identity())
        
        notify = 'notify' in params and params['notify']
        
        if not booking.local_id == local.id:
            abort(401, message = f'You are not allowed to confirm the booking [{booking.id}].')
        
        if not booking.status.status == PENDING_STATUS:
            status = StatusModel.query.get(booking.status_id)
            if not status: abort(500, message='The status was not found.')
            abort(409, message=f"The booking is '{status.name}'.")
        
        try:
            booking = confirmBooking(booking)
        except SQLAlchemyError as e:
            traceback.print_exc()
            rollback()
            abort(500, message = str(e) if DEBUG else 'Could not confirm the booking.')
            
        
        if notify:
            send_confirmed_mail_async(booking.local_id, booking.id)
            
        return booking
 
@blp.route('cancel/<int:booking_id>')
class BookingCancelId(MethodView):
    
    
    @blp.arguments(NotifyParams, location='query')
    @blp.arguments(CommentSchema)
    @blp.response(404, description='La reserva no existe.')
    @blp.response(401, description='No tienes permisos para cancelar la reserva.')
    @blp.response(204, BookingSchema)
    @jwt_required(refresh=True)
    def delete(self, params, data, booking_id):
        """
        Cancela una reserva por parte del local identificado por el token de refresco. Cambia el estado a cancelado.
        """
        booking = BookingModel.query.get_or_404(booking_id)
        
        local = LocalModel.query.get(get_jwt_identity())
        
        notify = 'notify' in params and params['notify']
        
        if not booking.local_id == local.id:
            abort(401, message = f'You are not allowed to cancel the booking [{booking.id}].')
        
        if booking.status.status == DONE_STATUS or booking.status.status == CANCELLED_STATUS:
            abort(409, message = f"The booking is '{booking.status.name}'.")
        
        comment = None
        
        if 'comment' in data:
            comment = data['comment']
        
        try:
            cancelBooking(booking, comment=comment)
            
            if notify:
                send_cancelled_mail_async(booking.local_id, booking.id)
            
            return {}
        except SQLAlchemyError as e:
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
    
    @blp.arguments(BookingSchema)
    @blp.response(404, description='El token de administrador no existe.')
    @blp.response(403, description='No tienes permisos para usar este endpoint.')
    @blp.response(401, description='Falta la cabecera de autorización.')
    @blp.response(201, NewBookingSchema)
    def post(self, booking_data):
        """
        [ADMIN PRIVATE] Crear una nueva reserva por parte del administrador del sistema.
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
        
        
        
        