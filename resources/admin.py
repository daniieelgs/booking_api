
from flask import request
import jwt
from helpers.LocalController import getLocals

from helpers.security import decodeJWT, generateTokens
from flask_smorest import Blueprint, abort
from flask.views import MethodView

from globals import ADMIN_IDENTITY, ADMIN_ROLE
from models.local import LocalModel
from models.session_token import SessionTokenModel
from schema import LocalAdminParams, LocalListSchema, LocalTokensSchema

blp = Blueprint('admin', __name__, description='Endpoints de administrador.')

@blp.route('tokens/local/<string:local_id>')
class LocalTokens(MethodView):

    @blp.response(404, description='El local no existe. El token administrativo no existe.')
    @blp.response(403, description='No tienes permisos para usar este endpoint.')
    @blp.response(401, description='Falta cabecera de autorización. El token ha expirado.')
    @blp.response(200, LocalTokensSchema)
    def post(self, local_id):
        """
        Devuelve tokens de sesión para el local.
        """
        
        token_header = request.headers.get('Authorization')

        if not token_header or not token_header.startswith('Bearer '):
            return abort(401, message='Missing Authorization Header')
        
        token = token_header.split(' ', 1)[1]
                
        try:
            token_decoded = decodeJWT(token)
        except jwt.exceptions.ExpiredSignatureError:
            abort(401, message = 'The token has expired.')
        
        identity = token_decoded['sub']
        id = token_decoded['token']
        
        if identity != ADMIN_IDENTITY:
            abort(403, message = 'You are not allowed to use this endpoint.')
        
        token = SessionTokenModel.query.get_or_404(id)
        
        local = LocalModel.query.get_or_404(local_id)
        
        if token.user_session.user != ADMIN_ROLE:
            abort(403, message = 'You are not allowed to use this endpoint.')
            
        access_token, refresh_token = generateTokens(local.id, local.id, access_token=True, refresh_token=True)
        
        return {'access_token': access_token, 'refresh_token': refresh_token, 'local': local}
    
@blp.route('local/all')
class LocalAll(MethodView):

    @blp.arguments(LocalAdminParams, location='query')
    @blp.response(404, description='El local no existe. El token administrativo no existe.')
    @blp.response(403, description='No tienes permisos para usar este endpoint.')
    @blp.response(401, description='Falta cabecera de autorización. El token ha expirado.')
    @blp.response(200, LocalListSchema)
    def get(self, params):
        """
        Devuelve todos los locales.
        """
        
        token_header = request.headers.get('Authorization')

        if not token_header or not token_header.startswith('Bearer '):
            return abort(401, message='Missing Authorization Header')
        
        token = token_header.split(' ', 1)[1]
        
        try:
            token_decoded = decodeJWT(token)
        except jwt.exceptions.ExpiredSignatureError:
            abort(401, message = 'The token has expired.')
        
        identity = token_decoded['sub']
        id = token_decoded['token']
        
        if identity != ADMIN_IDENTITY:
            abort(403, message = 'You are not allowed use this endpoint.')
        
        token = SessionTokenModel.query.get_or_404(id)
        
        if token.user_session.user != ADMIN_ROLE:
            abort(403, message = 'You are not allowed to use this endpoint.')
        
        locals = getLocals(params)
                
        return {'locals': locals, 'total': len(locals)}
        