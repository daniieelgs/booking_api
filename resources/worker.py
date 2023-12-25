from flask.views import MethodView
from flask_smorest import Blueprint, abort
from models import WorkGroupModel
from models.local import LocalModel
from models.worker import WorkerModel
from schema import WorkGroupSchema, WorkerSchema, WorkerWorkGroupSchema
from db import db, addAndCommit, deleteAndCommit, rollback
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
import traceback

from globals import DEBUG

blp = Blueprint('worker', __name__, description='Workers CRUD')

def getAllWorkers(local_id):
    workers = set()
    
    work_groups = LocalModel.query.get_or_404(local_id).work_groups
    
    for work_group in work_groups:
        for worker in work_group.workers:
            workers.add(worker)
    
    return workers

@blp.route('/local/<string:local_id>')
class WorkersGetAll(MethodView):

    @blp.response(404, description='The local was not found')
    @blp.response(200, WorkerSchema(many=True))
    def get(self, local_id):
        """
        Retrieves all workers.
        """      
        return getAllWorkers(local_id)
    
@blp.route('/local/<string:local_id>/work_group')
class WorkersGetAllWorkGroups(MethodView):

    @blp.response(404, description='The local was not found')
    @blp.response(200, WorkerWorkGroupSchema(many=True))
    def get(self, local_id):
        """
        Recover all workers with the work groups to which they belong.
        """                
        return getAllWorkers(local_id)
    
@blp.route('')
class Worker(MethodView):

    @blp.arguments(WorkerSchema)
    @blp.response(404, description='The local was not found. The work groups were not found or does not belong to the local session token.')
    @blp.response(201, WorkerWorkGroupSchema)
    @jwt_required(refresh=True)
    def post(self, worker_data):
        """
        Creates a new worker and add to work groups.
        """
        local = LocalModel.query.get(get_jwt_identity())
        
        if local is None:
            abort(404, message = f"The local [{get_jwt_identity()}] was not found.")
        
        work_groups_ids = worker_data.pop('work_groups')
        
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
    
    @blp.response(404, description='The local was not found')
    @blp.response(204, description='The workers were deleted')
    @jwt_required(fresh=True)
    def delete(self):
        """
        Deletes all workers.
        """
        try:
            workers = getAllWorkers(get_jwt_identity())
            if not workers:
                return {}

            deleteAndCommit(*workers)

        except SQLAlchemyError as e:
            traceback.print_exc()
            rollback()
            abort(500, message = str(e) if DEBUG else 'Could not delete the workers.')

@blp.route('/<int:worker_id>/work_group')
class WorkerWorkGroupByID(MethodView):

    @blp.response(404, description='The worker was not found')
    @blp.response(200, WorkerWorkGroupSchema)
    def get(self, worker_id):
        """
        Retrieves a worker by ID.
        """
        return WorkerModel.query.get_or_404(worker_id)

@blp.route('/<int:worker_id>')
class WorkerByID(MethodView):

    @blp.response(404, description='The worker was not found')
    @blp.response(200, WorkerSchema)
    def get(self, worker_id):
        """
        Retrieves a worker by ID.
        """
        return WorkerModel.query.get_or_404(worker_id)


    @blp.arguments(WorkerSchema)
    @blp.response(404, description='The worker was not found.')
    @blp.response(403, description='You are not allowed to update this worker.')
    @blp.response(200, WorkerWorkGroupSchema)
    @jwt_required(refresh=True)
    def put(self, worker_data, worker_id):
        """
        Updates a worker.
        """
        worker = WorkerModel.query.get_or_404(worker_id)
        
        if worker.work_groups.first().local_id != get_jwt_identity():
            abort(403, message = 'You are not allowed to update this work group.')
            
        work_groups_ids = worker_data.pop('work_groups')
        
        if not work_groups_ids:
            abort(404, message = f"The work groups were not found.")
            
        work_groups = []
            
        for id in work_groups_ids:
            work_group = WorkGroupModel.query.get(id)
            if work_group is None or work_group.local_id != get_jwt_identity():
                abort(404, message = f"The work group [{id}] was not found.")
            work_groups.append(work_group)
            
        worker.work_groups = work_groups
            
        for key, value in worker_data.items():
            setattr(worker, key, value)
        
        try:
            addAndCommit(worker)
        except SQLAlchemyError as e:
            traceback.print_exc()
            rollback()
            abort(500, message = str(e) if DEBUG else 'Could not update de work group.')
        return worker

    @blp.response(404, description='The worker was not found')
    @blp.response(403, description='You are not allowed to delete this worker')
    @blp.response(204, description='The worker was deleted')
    @jwt_required(fresh=True)
    def delete(self, worker_id):
        """
        Deletes a worker.
        """
        worker = WorkerModel.query.get_or_404(worker_id)
        
        if worker.work_groups.first().local_id != get_jwt_identity():
            abort(403, message = 'You are not allowed to delete this worker.')
        
        try:
            deleteAndCommit(worker)
        except SQLAlchemyError as e:
            traceback.print_exc()
            rollback()
            abort(500, message = str(e) if DEBUG else 'Could not delete the worker.')
        return {}