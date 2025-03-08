from flask.views import MethodView
from flask_smorest import Blueprint, abort
from helpers.BookingController import cancelBooking, getBookings
from helpers.DatetimeHelper import DATETIME_NOW
from helpers.error.LocalError.LocalNotFoundException import LocalNotFoundException
from models import WorkGroupModel
from models.local import LocalModel
from schema import DeleteParams, PublicWorkGroupWorkerListSchema, PublicWorkGroupWorkerSchema, WorkGroupListSchema, WorkGroupSchema, WorkGroupServiceListSchema, WorkGroupServiceSchema, WorkGroupWorkerListSchema, WorkGroupWorkerSchema
from db import db, addAndCommit, deleteAndCommit, rollback
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
import traceback
from datetime import datetime

from globals import CONFIRMED_STATUS, DEBUG, PENDING_STATUS

blp = Blueprint('work_group', __name__, description='CRUD de grupos de trabajo.')

@blp.route('/local/<string:local_id>')
class WorkGroupGetAll(MethodView):

    @blp.response(404, description='El local no existe.')
    @blp.response(200, WorkGroupListSchema)
    def get(self, local_id):
        """
        Devuelve todos los datos públicos de los grupos de trabajo de un local.
        """
        
        wg = list(LocalModel.query.get_or_404(local_id).work_groups)
        
        return {'work_groups': wg, 'total': len(wg)}
    
@blp.route('/local/<string:local_id>/workers')
class WorkGroupWorkersGetAll(MethodView):

    @blp.response(404, description='El local no existe.')
    @blp.response(200, PublicWorkGroupWorkerListSchema)
    def get(self, local_id):
        """
        Devuelve todos los datos públicos de los grupos de trabajo de un local con sus trabajadores.
        """
        wg = list(LocalModel.query.get_or_404(local_id).work_groups)
        
        return {"work_groups": wg, "total": len(wg)}
    
@blp.route('/workers')
class WorkGroupWorkersGetAll(MethodView):

    @blp.response(404, description='El local no existe.')
    @blp.response(200, WorkGroupWorkerListSchema)
    @jwt_required(refresh=True)
    def get(self):
        """
        Devuelve todos los datos de los grupos de trabajo del local identificado con el token de refresco con sus trabajadores.
        """
        
        wg = list(LocalModel.query.get_or_404(get_jwt_identity()).work_groups)
        
        return {"work_groups": wg, "total": len(wg)}
    
@blp.route('/local/<string:local_id>/services')
class WorkGroupServicesGetAll(MethodView):

    @blp.response(404, description='El local no existe.')
    @blp.response(200, WorkGroupServiceListSchema)
    def get(self, local_id):
        """
        Devuelve todos los datos públicos de los grupos de trabajo de un local con sus servicios.
        """
        
        wg = list(LocalModel.query.get_or_404(local_id).work_groups)
        
        return {"work_groups": wg, "total": len(wg)}
    
@blp.route('')
class WorkGroup(MethodView):

    @blp.arguments(WorkGroupSchema)
    @blp.response(404, description='El local no existe.')
    @blp.response(409, description='El nombre ya está en uso.')
    @blp.response(201, WorkGroupSchema)
    @jwt_required(refresh=True)
    def post(self, work_group_data):
        """
        Crea un nuevo grupo de trabajo en el local identificado con el token de refresco.
        """
        
        work_group = WorkGroupModel(**work_group_data)
        
        local = LocalModel.query.get_or_404(get_jwt_identity())
        
        work_group.local = local
        work_group.local_id = local.id
        
        try:
            addAndCommit(work_group)
        except IntegrityError as e:
            traceback.print_exc()
            rollback()
            abort(409, message = 'The name is already in use.')
        except SQLAlchemyError as e:
            traceback.print_exc()
            rollback()
            abort(500, message = str(e) if DEBUG else 'Could not create the work group.')
        return work_group
@blp.route('/<int:work_group_id>/workers')
class PublicWorkGroupWorkerByID(MethodView):

    @blp.response(404, description='El grupo de trabajo no existe.')
    @blp.response(200, PublicWorkGroupWorkerSchema)
    def get(self, work_group_id):
        """
        Devuelve los datos públicos de un grupo de trabajo identificado por ID con sus trabajadores.
        """
        return WorkGroupModel.query.get_or_404(work_group_id)
    
@blp.route('/private/<int:work_group_id>/workers')
class WorkGroupWorkerByID(MethodView):

    @blp.response(404, description='El grupo de trabajo no existe.')
    @blp.response(200, WorkGroupWorkerSchema)
    @jwt_required(refresh=True)
    def get(self, work_group_id):
        """
        Devuelve los datos de un grupo de trabajo identificado por ID con sus trabajadores.
        """
        work_group = WorkGroupModel.query.get_or_404(work_group_id)
        
        if work_group.local_id != get_jwt_identity():
            abort(403, message = 'You are not allowed to see this work group.')
        
        return work_group
    
@blp.route('/<int:work_group_id>/services')
class WorkGroupServicesByID(MethodView):

    @blp.response(404, description='El grupo de trabajo no existe.')
    @blp.response(200, WorkGroupServiceSchema)
    def get(self, work_group_id):
        """
        Devuelve los datos públicos de un grupo de trabajo identificado por ID con sus servicios.
        """
        return WorkGroupModel.query.get_or_404(work_group_id)

@blp.route('/<int:work_group_id>')
class WorkGroupByID(MethodView):

    @blp.response(404, description='El grupo de trabajo no existe.')
    @blp.response(200, WorkGroupSchema)
    def get(self, work_group_id):
        """
        Devuelve los datos de un grupo de trabajo identificado por ID.
        """
        return WorkGroupModel.query.get_or_404(work_group_id)


    @blp.arguments(WorkGroupSchema)
    @blp.response(404, description='El grupo de trabajo no existe.')
    @blp.response(403, description='No tienes permiso para actualizar este grupo de trabajo.')
    @blp.response(409, description='El nombre ya está en uso.')
    @blp.response(200, WorkGroupSchema)
    @jwt_required(refresh=True)
    def put(self, work_group_data, work_group_id):
        """
        Actualiza los datos de un grupo de trabajo identificado por ID.
        """
        work_group = WorkGroupModel.query.get_or_404(work_group_id)
        
        if work_group.local_id != get_jwt_identity():
            abort(403, message = 'You are not allowed to update this work group.')
            
        for key, value in work_group_data.items():
            setattr(work_group, key, value)
        try:
            addAndCommit(work_group)
        except IntegrityError as e:
            traceback.print_exc()
            rollback()
            abort(409, message = 'The name is already in use.')
        except SQLAlchemyError as e:
            traceback.print_exc()
            rollback()
            abort(500, message = str(e) if DEBUG else 'Could not update de work group.')
        return work_group

    @blp.arguments(DeleteParams, location='query')
    @blp.response(404, description='El grupo de trabajo no existe.')
    @blp.response(403, description='No tienes permiso para eliminar este grupo de trabajo.')
    @blp.response(409, description='El grupo de trabajo tiene trabajadores o reservas.')
    @blp.response(204, description='El grupo de trabajo ha sido eliminado.')
    @jwt_required(fresh=True)
    def delete(self, params, work_group_id):
        """
        Elimina un grupo de trabajo identificado por ID. Requiere token de acceso.
        """
        work_group = WorkGroupModel.query.get_or_404(work_group_id)
        
        if work_group.local_id != get_jwt_identity():
            abort(403, message = 'You are not allowed to delete this work group.')
        
        if work_group.workers.all():            
            abort(409, message = 'The work group has workers.')
        
        force = params['force'] if 'force' in params else False
        
        try:
            
            bookings = getBookings(work_group.local_id, datetime_init=DATETIME_NOW,datetime_end=None, status=[CONFIRMED_STATUS, PENDING_STATUS], work_group_id=work_group.id)
        
            if not force and bookings:
                abort(409, message = 'The work group has bookings.')
            elif force and bookings:
                for booking in bookings:
                    cancelBooking(booking, params['comment'] if 'comment' in params else None) #TODO add comment
            
            deleteAndCommit(work_group)
        except SQLAlchemyError as e:
            traceback.print_exc()
            rollback()
            abort(500, message = str(e) if DEBUG else 'Could not delete the work group.')
        except LocalNotFoundException as e:
            abort(404, message = str(e))
        return {}

