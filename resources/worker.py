from flask import request
from flask.views import MethodView
from flask_smorest import Blueprint, abort
from helpers.BookingController import cancelBooking, getBookings, searchWorkerBookings
from helpers.DatetimeHelper import DATETIME_NOW
from helpers.error.LocalError.LocalNotFoundException import LocalNotFoundException
from models import WorkGroupModel
from models.local import LocalModel
from models.worker import WorkerModel
from schema import DeleteParams, PublicWorkerListSchema, PublicWorkerSchema, PublicWorkerWorkGroupSchema, PublicWorkerWorkListGroupSchema, UpdateParams, WorkerListSchema, WorkerSchema, WorkerWorkGroupSchema
from db import addAndCommit, deleteAndCommit, rollback
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy.exc import SQLAlchemyError
import traceback

from globals import CONFIRMED_STATUS, DEBUG, PENDING_STATUS

blp = Blueprint('worker', __name__, description='CRUD de trabajadores.')

def getAllWorkers(local_id):
    workers = set()
    
    work_groups = LocalModel.query.get_or_404(local_id).work_groups
    
    for work_group in work_groups:
        for worker in work_group.workers:
            workers.add(worker)
    
    return workers

@blp.route('/local/<string:local_id>')
class WorkersGetAll(MethodView):

    @blp.response(404, description='El local no existe.')
    @blp.response(200, PublicWorkerListSchema)
    def get(self, local_id):
        """
        Devuelve todos los datos públicos de los trabajadores de un local.
        """      
        workers = getAllWorkers(local_id)
        return {"workers": workers, "total": len(workers)}
    
@blp.route('/local/<string:local_id>/work_group')
class WorkersGetAllWorkGroups(MethodView):

    @blp.response(404, description='El local no existe.')
    @blp.response(200, PublicWorkerWorkListGroupSchema)
    def get(self, local_id):
        """
        Devuelve todos los datos públicos de los trabajadores de un local con sus grupos de trabajo.
        """    
        workers = getAllWorkers(local_id)            
        return {"workers": workers, "total": len(workers)}
    
@blp.route('')
class Worker(MethodView):

    @blp.response(404, description='El local no existe.')
    @blp.response(200, WorkerListSchema)
    @jwt_required(refresh=True)
    def get(self):
        """
        Devuelve todos los datos de los trabajadores del local identificado con el token de refresco.
        """
        workers = getAllWorkers(get_jwt_identity())
        return {"workers": workers, "total": len(workers)}

    @blp.arguments(WorkerSchema)
    @blp.response(404, description='El local no existe, os grupos de trabajo no fueron encontrados o no pertenecen al local de la sesión.')
    @blp.response(201, WorkerWorkGroupSchema)
    @jwt_required(refresh=True)
    def post(self, worker_data):
        """
        Crea un nuevo trabajador y lo asocia a los grupos de trabajo.
        """
        local = LocalModel.query.get(get_jwt_identity())
        
        if local is None:
            abort(404, message = f"The local [{get_jwt_identity()}] was not found.")
        
        work_groups_ids = set(worker_data.pop('work_groups'))
                
        if not work_groups_ids:
            abort(404, message = f"The work groups were not found.")
        
        worker = WorkerModel(**worker_data)
        
        work_groups = []
        
        for id in work_groups_ids:
            work_group = WorkGroupModel.query.get(id)
            if work_group is None or work_group.local_id != local.id:
                abort(404, message = f"The work group [{id}] was not found.")
            work_groups.append(work_group)
            work_group.workers.append(worker)
        
        try:
            addAndCommit(worker, *work_groups)
        except SQLAlchemyError as e:
            traceback.print_exc()
            rollback()
            abort(500, message = str(e) if DEBUG else 'Could not create the worker.')
            
        return worker
    
@blp.route('/private/<int:worker_id>/work_group')
class WorkerWorkGroupByID(MethodView):

    @blp.response(404, description='El trabajador no existe.')
    @blp.response(200, WorkerWorkGroupSchema)
    @jwt_required(refresh=True)
    def get(self, worker_id):
        """
        Devuelve todos los datos de un trabajador con sus grupos de trabajo.
        """
        worker = WorkerModel.query.get_or_404(worker_id)
        
        if worker.work_groups.first().local_id != get_jwt_identity():
            abort(403, message = 'You are not allowed to access this worker.')
        
        return worker

@blp.route('/<int:worker_id>/work_group')
class PublicWorkerWorkGroupByID(MethodView):

    @blp.response(404, description='El trabajador no existe.')
    @blp.response(200, PublicWorkerWorkGroupSchema)
    def get(self, worker_id):
        """
        Devuelve todos los datos públicos de un trabajador con sus grupos de trabajo.
        """
        return WorkerModel.query.get_or_404(worker_id)

@blp.route('/private/<int:worker_id>')
class WorkerByID(MethodView):

    @blp.response(404, description='El trabajador no existe.')
    @blp.response(200, WorkerSchema)
    @jwt_required(refresh=True)
    def get(self, worker_id):
        """
        Devuelve todos los datos de un trabajador.
        """
        
        worker = WorkerModel.query.get_or_404(worker_id)
        
        if worker.work_groups.first().local_id != get_jwt_identity():
            abort(403, message = 'You are not allowed to access this worker.')
        
        return worker

@blp.route('/<int:worker_id>')
class PublicWorkerByID(MethodView):

    @blp.response(404, description='El trabajador no existe.')
    @blp.response(200, PublicWorkerSchema)
    def get(self, worker_id):
        """
        Devuelve todos los datos públicos de un trabajador.
        """
        return WorkerModel.query.get_or_404(worker_id)


    @blp.arguments(UpdateParams, location='query')
    @blp.arguments(WorkerSchema)
    @blp.response(404, description='El trabajador no existe.')
    @blp.response(409, description='El trabajador ya tiene reservas con el grupo de trabajo antiguo.')
    @blp.response(403, description='No tienes permiso para actualizar este trabajador.')
    @blp.response(200, WorkerWorkGroupSchema)
    @jwt_required(refresh=True)
    def put(self, params, worker_data, worker_id):
        """
        Actualiza un trabajador y lo asocia a los grupos de trabajo.
        """
        worker = WorkerModel.query.get_or_404(worker_id)
        
        if worker.work_groups.first().local_id != get_jwt_identity():
            abort(403, message = 'You are not allowed to update this work group.')
            
        work_groups_ids = set(worker_data.pop('work_groups'))
        
        if not work_groups_ids:
            abort(404, message = f"The work groups were not found.")
            
        work_groups = []
            
        for id in work_groups_ids:
            work_group = WorkGroupModel.query.get(id)
            if work_group is None or work_group.local_id != get_jwt_identity():
                abort(404, message = f"The work group [{id}] was not found.")
            work_groups.append(work_group)
            
        force = params['force'] if 'force' in params else False
        
        try:
                    
            if not force and work_groups != worker.work_groups:
                bookings = getBookings(get_jwt_identity(), datetime_init=DATETIME_NOW,datetime_end=None, status=[CONFIRMED_STATUS, PENDING_STATUS], worker_id=worker.id)
                
                if bookings:
                    abort(409, message = 'The worker has bookings with old work group.')
                
            worker.work_groups = work_groups
                
            for key, value in worker_data.items():
                setattr(worker, key, value)
        
            addAndCommit(worker)
        except SQLAlchemyError as e:
            traceback.print_exc()
            rollback()
            abort(500, message = str(e) if DEBUG else 'Could not update de work group.')
        except LocalNotFoundException as e:
            abort(404, message = str(e))
        return worker

    @blp.arguments(DeleteParams, location='query')
    @blp.response(404, description='El trabajador no existe.')
    @blp.response(403, description='No tienes permiso para eliminar este trabajador.')
    @blp.response(204, description='El trabajador ha sido eliminado.')
    @jwt_required(fresh=True)
    def delete(self, params, worker_id):
        """
        Elimina un trabajador identificado por ID. Requiere token de acceso.
        """
        worker = WorkerModel.query.get_or_404(worker_id)
        
        if worker.work_groups.first().local_id != get_jwt_identity():
            abort(403, message = 'You are not allowed to delete this worker.')
        
        force = params['force'] if 'force' in params else False
        
        try:
        
            bookings = getBookings(get_jwt_identity(), datetime_init=DATETIME_NOW,datetime_end=None, status=[CONFIRMED_STATUS, PENDING_STATUS], worker_id=worker.id)
            
            if not force and bookings:
                abort(409, message = 'The work group has bookings.')
            elif force and bookings:
                for booking in bookings:
                    workers = [worker for worker in list(booking.services[0].work_group.workers.all()) if worker.id != worker_id]
                    worker_id = searchWorkerBookings(get_jwt_identity(), booking.datetime_init, booking.datetime_end, workers, booking.id)
                    if worker_id:
                        booking.worker_id = worker_id
                    else:
                        cancelBooking(booking, params['comment'] if 'comment' in params else None)
        
            if force: addAndCommit(*bookings)
            deleteAndCommit(worker)
        except SQLAlchemyError as e:
            traceback.print_exc()
            rollback()
            abort(500, message = str(e) if DEBUG else 'Could not delete the worker.')
        except LocalNotFoundException as e:
            abort(404, message = str(e))
        return {}