import traceback

from flask_jwt_extended import get_jwt_identity, jwt_required
from flask_smorest import Blueprint, abort
from flask.views import MethodView
from sqlalchemy.exc import SQLAlchemyError, IntegrityError

from db import addAndFlush, commit, deleteAndCommit, addAndCommit, rollback

from globals import CONFIRMED_STATUS, DEBUG, PENDING_STATUS
from helpers.BookingController import cancelBooking, createOrUpdateBooking, deserializeBooking, getBookings
from helpers.DatetimeHelper import DATETIME_NOW
from helpers.error.BookingError.AlredyBookingException import AlredyBookingExceptionException
from helpers.error.BookingError.LocalUnavailableException import LocalUnavailableException
from helpers.error.LocalError.LocalNotFoundException import LocalNotFoundException
from models.service import ServiceModel

from models import LocalModel
from models.work_group import WorkGroupModel
from schema import DeleteParams, ServiceSchema, ServiceWorkGroup, ServiceWorkGroupListSchema, UpdateParams

from datetime import datetime

blp = Blueprint('service', __name__, description='CRUD de servicios.')

def getAllServices(local_id):
    work_groups = LocalModel.query.get_or_404(local_id).work_groups.all()
    
    services = []
    
    for wg in work_groups:
        for service in wg.services.all():
            services.append(service)
    
    return services

@blp.route('local/<string:local_id>')
class AllServices(MethodView):

    @blp.response(404, description='El local no existe.')
    @blp.response(200, ServiceWorkGroupListSchema)
    def get(self, local_id):
        """
        Devuelve todos los datos públicos de servicios de un local.
        """
        services = getAllServices(local_id)
        return {'services': services, "total": len(services)}
    
@blp.route('<int:service_id>')
class ServiceById(MethodView):

    @blp.response(404, description='El servicio no existe.')
    @blp.response(200, ServiceWorkGroup)
    def get(self, service_id):
        """
        Devuelve todos los datos del servicio.
        """
        return ServiceModel.query.get_or_404(service_id)
    
    @blp.arguments(UpdateParams, location='query')
    @blp.arguments(ServiceSchema)
    @blp.response(404, description='El servicio no existe, el grupo de trabajo no existe o el grupo de trabajo no pertenece al local.')
    @blp.response(403, description='No tienes permisos para actualizar este servicio.')
    @blp.response(409, description='El servicio ya existe, el servicio tiene reservas con trabajadores en diferentes grupos de trabajo, lLa nueva duración no es compatible con las reservas o el servicio tiene reservas.')
    @blp.response(200, ServiceWorkGroup)
    @jwt_required(refresh=True)
    def put(self, params, service_data, service_id):
        """
        Actualiza los datos del servicio.
        """
        service = ServiceModel.query.get_or_404(service_id)
        
        if service.work_group.local_id != get_jwt_identity():
            abort(403, message = "You are not allowed to update this service.")
        
        work_group_id = service_data.pop('work_group')
        
        work_group = WorkGroupModel.query.get(work_group_id)
        if work_group is None or work_group.local_id != get_jwt_identity():
            abort(404, message = f"The work group [{work_group_id}] was not found.")
                    
        force = params['force'] if 'force' in params else False
                    
        if not force and work_group_id != service.work_group_id:
            bookings = getBookings(get_jwt_identity(), datetime_init=DATETIME_NOW,datetime_end=None, status=[CONFIRMED_STATUS, PENDING_STATUS], service_id=service.id)
            
            bookings = [booking for booking in bookings if work_group not in list(booking.worker.work_groups.all())]
            
            if bookings:
                abort(409, message = 'The service has bookings with workers on differents work group.')
            
        check_booking = service.duration != service_data['duration']
                                        
        for key, value in service_data.items():
            setattr(service, key, value)
            
        service.work_group = work_group
            
        try:
            addAndFlush(service)
            
            bookings = getBookings(get_jwt_identity(), datetime_init=DATETIME_NOW,datetime_end=None, status=[CONFIRMED_STATUS, PENDING_STATUS], service_id=service.id)
            
            if check_booking and not force:
                for booking in bookings:
                    try:
                        createOrUpdateBooking(deserializeBooking(booking), get_jwt_identity(), booking)
                    except (LocalUnavailableException, AlredyBookingExceptionException) as e:
                        abort(409, message = f"The service has bookings that can not be updated. Booking [{booking.id}]: '{str(e)}'")
            
            commit()
        except IntegrityError as e:
            traceback.print_exc()
            rollback()
            abort(409, message = str(e) if DEBUG else 'Could not update the service.')
        except SQLAlchemyError as e:
            traceback.print_exc()
            rollback()
            abort(500, message = str(e) if DEBUG else 'Could not update the service.')
        except LocalNotFoundException as e:
            abort(404, message = str(e))
            
        return service
    
    @blp.arguments(DeleteParams, location='query')
    @blp.response(404, description='El servicio no existe.')
    @blp.response(403, description='No tienes permisos para eliminar este servicio.')
    @blp.response(204, description='El servicio ha sido eliminado.')
    @jwt_required(fresh=True)
    def delete(self, params, service_id):
        """
        Elimina un servicio identificado por ID. Requiere token de acceso.
        """
        
        service = ServiceModel.query.get_or_404(service_id)
        
        if service.work_group.local_id != get_jwt_identity():
            abort(403, message = "You are not allowed to delete this service.")
        
        force = params['force'] if 'force' in params else False
        
        try:
            
            bookings = getBookings(get_jwt_identity(), datetime_init=DATETIME_NOW,datetime_end=None, status=[CONFIRMED_STATUS, PENDING_STATUS], service_id=service.id)
            
            if not force and bookings:
                abort(409, message = 'The service has bookings.')
            elif force and bookings:
                for booking in bookings:
                    cancelBooking(booking, params['comment'] if 'comment' in params else None)
            
            deleteAndCommit(service)
            return {}
        except SQLAlchemyError as e:
            traceback.print_exc()
            rollback()
            abort(500, message = str(e) if DEBUG else 'Could not delete the service.')
        except LocalNotFoundException as e:
            abort(404, message = str(e))
    
@blp.route('')
class Service(MethodView):

    @blp.arguments(ServiceSchema)
    @blp.response(409, description='El servicio ya existe.')
    @blp.response(404, description='El grupo de trabajo no existe o el grupo de trabajo no pertenece al local.')
    @blp.response(201, ServiceWorkGroup)
    @jwt_required(refresh=True)
    def post(self, service_data):
        """
        Crea un nuevo servicio.
        """
        
        local = LocalModel.query.get(get_jwt_identity())
        
        if local is None:
            abort(404, message = f"The local [{get_jwt_identity()}] was not found.")
        
        work_group_id = service_data.pop('work_group')
                    
        work_group = WorkGroupModel.query.get(work_group_id)
        if work_group is None or work_group.local_id != local.id:
            abort(404, message = f"The work group [{work_group_id}] was not found.")
        
        service = ServiceModel(**service_data)
        service.work_group = work_group
        
        try:
            addAndCommit(service)
        except IntegrityError as e:
            traceback.print_exc()
            rollback()
            abort(409, message = str(e) if DEBUG else 'Service alredy exists.')
        except SQLAlchemyError as e:
            traceback.print_exc()
            rollback()
            abort(500, message = str(e) if DEBUG else 'Could not create the service.')
        
        return service
    
    @blp.response(404, description='El local no existe.')
    @blp.response(204, description='Servicios eliminados.')
    @jwt_required(fresh=True)
    def delete(self):
        """
        Elimina todos los servicios de un local. Requiere token de acceso.
        """
        try:
            deleteAndCommit(*getAllServices(get_jwt_identity()))
            return {}
        except SQLAlchemyError as e:
            traceback.print_exc()
            rollback()
            abort(500, message = str(e) if DEBUG else 'Could not delete the services.')
    
    
    
