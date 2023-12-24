from flask import abort
from flask.views import MethodView
from flask_smorest import Blueprint
from models import WorkGroupModel
from models.local import LocalModel
from schema import WorkGroupSchema
from db import db, addAndCommit, deleteAndCommit, rollback
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy.exc import SQLAlchemyError
import traceback

from globals import DEBUG

blp = Blueprint('work_group', __name__, description='Work groups CRUD')

@blp.route('/<string:local_id>')
class WorkGroupGetAll(MethodView):

    @blp.response(404, description='The local was not found')
    @blp.response(200, WorkGroupSchema(many=True))
    def get(self, local_id):
        """
        Retrieves all work groups.
        """
        return LocalModel.query.get_or_404(local_id).work_groups
    
@blp.route('')
class WorkGroup(MethodView):

    #TODO: no poder crear dos work groups con el mismo nombre y local
    @blp.arguments(WorkGroupSchema)
    @blp.response(404, description='The local was not found')
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

@blp.route('/<int:work_group_id>')
class WorkGroupByID(MethodView):

    @blp.response(404, description='The work group was not found')
    @blp.response(200, WorkGroupSchema)
    def get(self, work_group_id):
        """
        Retrieves a work group by ID.
        """
        return WorkGroupModel.query.get_or_404(work_group_id)


    #TODO: no poder crear dos work groups con el mismo nombre y local
    @blp.arguments(WorkGroupSchema)
    @blp.response(404, description='The work group was not found')
    @blp.response(403, description='You are not allowed to update this work group')
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
            abort(500, message = str(e) if DEBUG else 'Could not create the local.')
        return {}
