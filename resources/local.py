
import traceback
from flask import request

from flask_jwt_extended import get_jwt, get_jwt_identity, jwt_required
from pytz import UnknownTimeZoneError
from helpers.DatetimeHelper import now
from helpers.path import createPathFromLocal, removePath
from helpers.security import decodeJWT, generatePassword, generateTokens, generateUUID, logOutAll
from flask_smorest import Blueprint, abort
from flask.views import MethodView
from sqlalchemy.exc import SQLAlchemyError, IntegrityError

from passlib.hash import pbkdf2_sha256

from db import deleteAndCommit, addAndCommit, rollback

from globals import ADMIN_IDENTITY, ADMIN_ROLE, DEBUG, LOCAL_ROLE
from models.session_token import SessionTokenModel
from schema import LocalSchema, LocalTokensSchema, LoginLocalSchema, PublicLocalSchema

from models import LocalModel

blp = Blueprint('local', __name__, description='local CRUD')
    
@blp.route('<string:local_id>')
class Local(MethodView):

    @blp.response(404, description='The local does not exist')
    @blp.response(200, PublicLocalSchema)
    def get(self, local_id):
        """
        Returns the public local data
        """
        return LocalModel.query.get_or_404(local_id)
@blp.route('')
class Local(MethodView):

    @blp.response(404, description='The local does not exist')
    @blp.response(200, LocalSchema)
    @jwt_required(refresh=True)
    def get(self):
        """
        Returns the local data
        """
        return LocalModel.query.get_or_404(get_jwt_identity())
    
    
    @blp.arguments(LocalSchema)
    @blp.response(400, description='The timezone is not valid.')
    @blp.response(409, description='The email is already in use.')
    @blp.response(404, description='The token does not exist.')
    @blp.response(403, description='You are not allowed to create a local.')
    @blp.response(401, description='Missing Authorization Header.')
    @blp.response(201, LocalTokensSchema)
    def post(self, local_data):
        """
        Creates a new local.
        If the password is not present, it will generate a new one and return it
        """
        
        token_header = request.headers.get('Authorization')

        if not token_header or not token_header.startswith('Bearer '):
            return abort(401, message='Missing Authorization Header')
        
        token = token_header.split(' ', 1)[1]
        
        identity = decodeJWT(token)['sub']
        id = decodeJWT(token)['token']
        
        if identity != ADMIN_IDENTITY:
            abort(403, message = 'You are not allowed to create a local.')
        
        token = SessionTokenModel.query.get(id)
        
        if not token:
            abort(403, message = 'The token does not exist.')
        
        if token.user_session.user != ADMIN_ROLE:
            abort(403, message = 'You are not allowed to create a local.')
        
        show_password = 'password' not in local_data
        
        if show_password: local_data['password'] = generatePassword()
        
        local_data['id'] = generateUUID()
                
        try:
            now(local_data['location'])
        except UnknownTimeZoneError as e:
            traceback.print_exc()
            abort(400, message = 'The timezone is not valid.')
        
        local = LocalModel(**local_data)
        
        local.password = pbkdf2_sha256.hash(local.password)

        try:
            addAndCommit(local)
            createPathFromLocal(local.id)
            access_token, refresh_token = generateTokens(local.id, local.id, access_token=True, refresh_token=True)
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
        
        for key, value in local_data.items():
            setattr(local, key, value)
        
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
            removePath(get_jwt_identity())
        except Exception as e:
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
        """
        Login a local with email and password
        """
        
        local = LocalModel.query.filter_by(email=login_data['email']).first()
        
        if not local or not pbkdf2_sha256.verify(login_data['password'], local.password):
            abort(401, message = 'Invalid credentials.')
            
        access_token, refresh_token = generateTokens(local.id, local.id, access_token=True, refresh_token=True)
            
        return {'access_token': access_token, 'refresh_token': refresh_token, 'local': local}
        
@blp.route('/logout')
class LocalLogout(MethodView):
    
    @jwt_required(refresh=True)
    @blp.response(204, description='Logout user and expire the refresh-token')
    def post(self):
        """
        Logout user and expire the refresh-token
        """
        tokenId = get_jwt().get('token')
        
        deleteAndCommit(SessionTokenModel.query.get(tokenId))
        
        return {}
    
@blp.route('/logout/all')
class LocalLogoutAll(MethodView):
    
    @jwt_required(refresh=True)
    @blp.response(204, description='Logout user and expire all the refresh-token')
    def post(self):
        """
        Logout user and expire all refresh-tokens
        """
        try:
            logOutAll(get_jwt_identity())
        except SQLAlchemyError as e:
            traceback.print_exc()
            rollback()
            abort(500, message = str(e) if DEBUG else 'Could not log-out all tokens.')
        
        return {}
    
@blp.route('/refresh')
class LocalRefresh(MethodView):
    
    @jwt_required(refresh=True)
    @blp.response(200, LocalTokensSchema)
    def post(self):
        """
        Refresh the refresh-token
        """
        token = get_jwt()
        tokenId = token.get('token')
        
        token = SessionTokenModel.query.get_or_404(tokenId)
        
        if token.user_session.user != LOCAL_ROLE:
            abort(403, message = 'You are not allowed to refresh this token.')
        
        refresh_token = generateTokens(get_jwt_identity(), get_jwt_identity(), refresh_token=True)
        return {'refresh_token': refresh_token}