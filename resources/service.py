import traceback

from flask_jwt_extended import get_jwt, get_jwt_identity, jwt_required
from helpers.security import generatePassword, generateTokens, generateUUID, logOutAll
from flask import make_response, request
from flask_smorest import Blueprint, abort
from flask.views import MethodView
from sqlalchemy.exc import SQLAlchemyError, IntegrityError

from passlib.hash import pbkdf2_sha256

from db import deleteAndCommit, addAndCommit, rollback

from globals import DEBUG
from models.service import ServiceModel
from models.session_token import SessionTokenModel

from models import LocalModel
from models.work_group import WorkGroupModel
from schema import ServiceSchema, ServiceWorkGroup

blp = Blueprint('service', __name__, description='service CRUD')

def getAllServices(local_id):
    work_groups = LocalModel.query.get_or_404(local_id).work_groups.all()
    
    services = []
    
    for wg in work_groups:
        for service in wg.services.all():
            services.append(service)
    
    return services

@blp.route('local/<string:local_id>')
class AllServices(MethodView):

    @blp.response(404, description='The local does not exist')
    @blp.response(200, ServiceWorkGroup(many=True))
    def get(self, local_id):
        """
        Returns all services of a local
        """
        return getAllServices(local_id)
    
@blp.route('<int:service_id>')
class ServiceById(MethodView):

    @blp.response(404, description='The service does not exist')
    @blp.response(200, ServiceWorkGroup)
    def get(self, service_id):
        """
        Returns the service
        """
        return ServiceModel.query.get_or_404(service_id)
    
    @blp.arguments(ServiceSchema)
    @blp.response(404, description='The service does not exist')
    @blp.response(403, description='You are not allowed to update this service')
    @blp.response(409, description='The service already exists')
    @blp.response(200, ServiceWorkGroup)
    @jwt_required(refresh=True)
    def put(self, service_data, service_id):
        """
        Updates the service
        """
        service = ServiceModel.query.get_or_404(service_id)
        
        if service.work_group.local_id != get_jwt_identity():
            abort(403, message = "You are not allowed to update this service.")
        
        work_group_id = service_data.pop('work_group')
        
        work_group = WorkGroupModel.query.get(work_group_id)
        if work_group is None or work_group.local_id != get_jwt_identity():
            abort(404, message = f"The work group [{work_group_id}] was not found.")
                    
        for key, value in service_data.items():
            setattr(service, key, value)
            
        service.work_group = work_group
            
        try:
            addAndCommit(service)
        except IntegrityError as e:
            traceback.print_exc()
            rollback()
            abort(409, message = str(e) if DEBUG else 'Could not update the service.')
        except SQLAlchemyError as e:
            traceback.print_exc()
            rollback()
            abort(500, message = str(e) if DEBUG else 'Could not update the service.')
            
        return service
    
    @blp.response(404, description='The service does not exist')
    @blp.response(403, description='You are not allowed to delete this service')
    @blp.response(204, description='The service was deleted')
    @jwt_required(fresh=True)
    def delete(self, service_id):
        """
        Deletes the service
        """
        
        service = ServiceModel.query.get_or_404(service_id)
        
        if service.work_group.local_id != get_jwt_identity():
            abort(403, message = "You are not allowed to delete this service.")
        
        try:
            deleteAndCommit(service)
            return {}
        except SQLAlchemyError as e:
            traceback.print_exc()
            rollback()
            abort(500, message = str(e) if DEBUG else 'Could not delete the service.')
    
@blp.route('')
class Service(MethodView):

    #TODO : restringir servicios con el mismo nombre en el mismo grupo de trabajo
    @blp.arguments(ServiceSchema)
    @blp.response(409, description='The service already exists')
    @blp.response(404, description='The local does not exist. The work group does not exist')
    @blp.response(201, ServiceWorkGroup)
    @jwt_required(refresh=True)
    def post(self, service_data):
        """
        Creates a new service.
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
    
    @blp.response(404, description='The local does not exist')
    @blp.response(204, description='The services were deleted')
    @jwt_required(fresh=True)
    def delete(self):
        """
        Deletes all services from a local
        """
        try:
            deleteAndCommit(*getAllServices(get_jwt_identity()))
            return {}
        except SQLAlchemyError as e:
            traceback.print_exc()
            rollback()
            abort(500, message = str(e) if DEBUG else 'Could not delete the services.')
    
    
    
