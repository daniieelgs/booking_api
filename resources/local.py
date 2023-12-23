
import datetime
import traceback

from flask_jwt_extended import get_jwt, get_jwt_identity, jwt_required
from helpers.security import generatePassword, generateTokens, generateUUID, logOutAll
from flask import make_response, request
from flask_smorest import Blueprint, abort
from flask.views import MethodView
from sqlalchemy.exc import SQLAlchemyError, IntegrityError

from passlib.hash import pbkdf2_sha256

from db import db, deleteAndCommit, addAndCommit, rollback

from globals import DEBUG
from models.session_token import SessionTokenModel
from schema import LocalSchema, LocalTokensSchema, LoginLocalSchema

from models import LocalModel

blp = Blueprint('local', __name__, description='local CRUD')

@blp.route('')
class Local(MethodView):
    #TODO crear admin token para poder crear listar y eliminar locales
    
    
    @blp.response(404, description='The local does not exist')
    @blp.response(200, LocalSchema)
    @jwt_required(refresh=True)
    def get(self):
        """
        Returns the local data
        """
        return LocalModel.query.get_or_404(get_jwt_identity())
    
    
    @blp.arguments(LocalSchema)
    @blp.response(409, description='The email is already in use')
    @blp.response(404, description='The local does not exist')
    @blp.response(201, LocalTokensSchema)
    def post(self, local_data):
        """
        Creates a new local.
        If the password is not present, it will generate a new one and return it
        """
        
        show_password = 'password' not in local_data
        
        if show_password: local_data['password'] = generatePassword()
        
        local_data['id'] = generateUUID()
        
        local = LocalModel(**local_data)
        
        local.password = pbkdf2_sha256.hash(local.password)

        try:
            addAndCommit(local)
            access_token, refresh_token = generateTokens(local.id, access_token=True, refresh_token=True)
        except IntegrityError as e:
            traceback.print_exc()
            rollback()
            abort(409, message = 'The email is already in use.')
        except SQLAlchemyError as e:
            traceback.print_exc()
            rollback()
            abort(500, message = str(e) if DEBUG else 'Could not create the local.')

        if show_password: local.password_generated = local_data['password']
        
        print(local)
        
        return {'access_token': access_token, 'refresh_token': refresh_token, 'local': local}
    
    @blp.arguments(LocalSchema)
    @blp.response(409, description='The email is already in use')
    @blp.response(404, description='The local does not exist')
    @blp.response(200, LocalSchema)
    @jwt_required(fresh=True)
    def put(self, local_data):
        """
        Updates the local data
        """
        
        local = LocalModel.query.get_or_404(get_jwt_identity())
        
        local.name = local_data['name']
        local.tlf = local_data['tlf']
        local.email = local_data['email']
        local.address = local_data['address']
        local.postal_code = local_data['postal_code']
        local.village = local_data['village']
        local.province = local_data['province']
        local.location = local_data['location']
        if 'password' in local_data: local.password = pbkdf2_sha256.hash(local_data['password'])
        
        
        try:
            addAndCommit(local)
        except IntegrityError as e:
            traceback.print_exc()
            rollback()
            abort(409, message = 'The email is already in use.')
        except SQLAlchemyError as e:
            traceback.print_exc()
            rollback()
            abort(500, message = str(e) if DEBUG else 'Could not update the local.')
        
        return local
    
    @blp.response(409, description='The email is already in use')
    @blp.response(404, description='The local does not exist')
    @blp.response(204, description='The local was deleted')
    @jwt_required(fresh=True)
    def delete(self):
        """
        Deletes the local
        """
        
        local = LocalModel.query.get_or_404(get_jwt_identity())
        
        try:
            deleteAndCommit(local)
        except SQLAlchemyError as e:
            traceback.print_exc()
            rollback()
            abort(500, message = str(e) if DEBUG else 'Could not delete the local.')
        
        return {}
    
@blp.route('/login')
class AccessLocal(MethodView):
    
    @blp.arguments(LoginLocalSchema)
    @blp.response(401, description='Invalid credentials')
    @blp.response(200, LocalTokensSchema)
    def post(self, login_data):
        
        local = LocalModel.query.filter_by(email=login_data['email']).first()
        
        if not local or not pbkdf2_sha256.verify(login_data['password'], local.password):
            abort(401, message = 'Invalid credentials.')
            
        access_token, refresh_token = generateTokens(local.id, access_token=True, refresh_token=True)
            
        return {'access_token': access_token, 'refresh_token': refresh_token, 'local': local}
        
@blp.route('/logout')
class LocalLogout(MethodView):
    
    @jwt_required(refresh=True)
    @blp.response(204, description='Logout user and expire the refresh-token')
    def post(self):
        tokenId = get_jwt().get('token')
        
        deleteAndCommit(SessionTokenModel.query.get(tokenId))
        
        return {}
    
@blp.route('/logout/all')
class LocalLogoutAll(MethodView):
    
    @jwt_required(refresh=True)
    @blp.response(204, description='Logout user and expire all the refresh-token')
    def post(self):
        
        try:
            logOutAll(get_jwt_identity())
        except SQLAlchemyError as e:
            traceback.print_exc()
            rollback()
            abort(500, message = str(e) if DEBUG else 'Could not log-out all tokens.')
        
        return {}