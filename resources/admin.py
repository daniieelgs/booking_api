
from flask import request

from helpers.security import decodeJWT, generateTokens
from flask_smorest import Blueprint, abort
from flask.views import MethodView

from globals import ADMIN_IDENTITY, ADMIN_ROLE
from models.local import LocalModel
from models.session_token import SessionTokenModel
from schema import LocalSchema, LocalTokensSchema

blp = Blueprint('admin', __name__)

@blp.route('tokens/local/<string:local_id>')
class LocalTokens(MethodView):

    @blp.response(404, description='The local does not exist. The token does not exist.')
    @blp.response(403, description='You are not allowed to use this endpoint.')
    @blp.response(401, description='Missing Authorization Header.')
    @blp.response(200, LocalTokensSchema)
    def post(self, local_id):
        """
        Returns the local tokens
        """
        
        token_header = request.headers.get('Authorization')

        if not token_header or not token_header.startswith('Bearer '):
            return abort(401, message='Missing Authorization Header')
        
        token = token_header.split(' ', 1)[1]
        
        identity = decodeJWT(token)['sub']
        id = decodeJWT(token)['token']
        
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

    @blp.response(404, description='The token does not exist.')
    @blp.response(403, description='You are not allowed to use this endpoint.')
    @blp.response(401, description='Missing Authorization Header.')
    @blp.response(200, LocalSchema(many=True))
    def get(self):
        """
        Returns all locals.
        """
        
        token_header = request.headers.get('Authorization')

        if not token_header or not token_header.startswith('Bearer '):
            return abort(401, message='Missing Authorization Header')
        
        token = token_header.split(' ', 1)[1]
        
        identity = decodeJWT(token)['sub']
        id = decodeJWT(token)['token']
        
        if identity != ADMIN_IDENTITY:
            abort(403, message = 'You are not allowed use this endpoint.')
        
        token = SessionTokenModel.query.get_or_404(id)
        
        if token.user_session.user != ADMIN_ROLE:
            abort(403, message = 'You are not allowed to use this endpoint.')
                
        return LocalModel.query.all()
        