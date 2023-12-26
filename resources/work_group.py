from flask.views import MethodView
from flask_smorest import Blueprint, abort
from models import WorkGroupModel
from models.local import LocalModel
from schema import WorkGroupSchema, WorkGroupServiceSchema, WorkGroupWorkerSchema
from db import db, addAndCommit, deleteAndCommit, rollback
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
import traceback

from globals import DEBUG

blp = Blueprint('work_group', __name__, description='Work groups CRUD')

@blp.route('/local/<string:local_id>')
class WorkGroupGetAll(MethodView):

    @blp.response(404, description='The local was not found')
    @blp.response(200, WorkGroupSchema(many=True))
    def get(self, local_id):
        """
        Retrieves all work groups.
        """
        return LocalModel.query.get_or_404(local_id).work_groups
    
@blp.route('/local/<string:local_id>/workers')
class WorkGroupWorkersGetAll(MethodView):

    @blp.response(404, description='The local was not found')
    @blp.response(200, WorkGroupWorkerSchema(many=True))
    def get(self, local_id):
        """
        Retrieves all work groups with their workers.
        """
        return LocalModel.query.get_or_404(local_id).work_groups
    
@blp.route('/local/<string:local_id>/services')
class WorkGroupServicesGetAll(MethodView):

    @blp.response(404, description='The local was not found')
    @blp.response(200, WorkGroupServiceSchema(many=True))
    def get(self, local_id):
        """
        Retrieves all work groups with their services.
        """
        return LocalModel.query.get_or_404(local_id).work_groups
    
@blp.route('')
class WorkGroup(MethodView):

    @blp.arguments(WorkGroupSchema)
    @blp.response(404, description='The local was not found')
    @blp.response(409, description='The name is already in use')
    @blp.response(201, WorkGroupSchema)
    @jwt_required(refresh=True)
    def post(self, work_group_data):
        """
        Creates a new work group.
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
    
    @blp.response(404, description='The local was not found')
    @blp.response(204, description='The work groups were deleted')
    @jwt_required(fresh=True)
    def delete(self):
        """
        Deletes all work groups.
        """
        try:
            work_groups = LocalModel.query.get_or_404(get_jwt_identity()).work_groups
            if not work_groups:
                return {}

            deleteAndCommit(*work_groups)

        except SQLAlchemyError as e:
            traceback.print_exc()
            rollback()
            abort(500, message = str(e) if DEBUG else 'Could not delete the work groups.')

@blp.route('/<int:work_group_id>/workers')
class WorkGroupWorkerByID(MethodView):

    @blp.response(404, description='The work group was not found')
    @blp.response(200, WorkGroupWorkerSchema)
    def get(self, work_group_id):
        """
        Retrieves a work group by ID with their workers.
        """
        return WorkGroupModel.query.get_or_404(work_group_id)
    
@blp.route('/<int:work_group_id>/services')
class WorkGroupServicesByID(MethodView):

    @blp.response(404, description='The work group was not found')
    @blp.response(200, WorkGroupServiceSchema)
    def get(self, work_group_id):
        """
        Retrieves a work group by ID with their services.
        """
        return WorkGroupModel.query.get_or_404(work_group_id)

@blp.route('/<int:work_group_id>')
class WorkGroupByID(MethodView):

    @blp.response(404, description='The work group was not found')
    @blp.response(200, WorkGroupSchema)
    def get(self, work_group_id):
        """
        Retrieves a work group by ID.
        """
        return WorkGroupModel.query.get_or_404(work_group_id)


    @blp.arguments(WorkGroupSchema)
    @blp.response(404, description='The work group was not found')
    @blp.response(403, description='You are not allowed to update this work group')
    @blp.response(409, description='The name is already in use')
    @blp.response(200, WorkGroupSchema)
    @jwt_required(refresh=True)
    def put(self, work_group_data, work_group_id):
        """
        Updates a work group.
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

    @blp.response(404, description='The work group was not found')
    @blp.response(403, description='You are not allowed to delete this work group')
    @blp.response(204, description='The work group was deleted')
    @jwt_required(fresh=True)
    def delete(self, work_group_id):
        """
        Deletes a work group.
        """
        work_group = WorkGroupModel.query.get_or_404(work_group_id)
        
        if work_group.local_id != get_jwt_identity():
            abort(403, message = 'You are not allowed to delete this work group.')
        
        try:
            deleteAndCommit(work_group)
        except SQLAlchemyError as e:
            traceback.print_exc()
            rollback()
            abort(500, message = str(e) if DEBUG else 'Could not delete the work group.')
        return {}

