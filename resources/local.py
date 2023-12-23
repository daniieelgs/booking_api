
import datetime
import traceback
from helpers.security import generatePassword, generateTokens, generateUUID
from flask import make_response, request
from flask_smorest import Blueprint, abort
from flask.views import MethodView
from sqlalchemy.exc import SQLAlchemyError, IntegrityError

from passlib.hash import pbkdf2_sha256

from db import db, deleteAndCommit, addAndCommit

from globals import DEBUG
from schema import LocalSchema, LocalTokensSchema

from models import LocalModel

blp = Blueprint('local', __name__, description='local CRUD')

@blp.route('')
class Local(MethodView):
    #TODO crear admin token para poder crear listar y eliminar locales
    
    
    def get(self):
        raise NotImplementedError()
    
    
    @blp.arguments(LocalSchema)
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
        except SQLAlchemyError as e:
            traceback.print_exc()
            abort(500, message = str(e) if DEBUG else 'Could not create the local.')

        if show_password: local.password_generated = local_data['password']
        
        print(local)
        
        return {'access_token': access_token, 'refresh_token': refresh_token, 'local': local}