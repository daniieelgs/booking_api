
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

from db import addAndFlush, commit, deleteAndCommit, addAndCommit, deleteAndFlush, rollback

from globals import ADMIN_IDENTITY, ADMIN_ROLE, DEBUG, LOCAL_ROLE, MIN_TIMEOUT_CONFIRM_BOOKING, TIMEOUT_CONFIRM_BOOKING
from models.local_settings import LocalSettingsModel
from models.session_token import SessionTokenModel
from models.smtp_settings import SmtpSettingsModel
from schema import LocalPatchSchema, LocalSchema, LocalTokensSchema, LocalWarningSchema, LoginLocalSchema, PublicLocalSchema, SmtpSettingsSchema

from models import LocalModel

blp = Blueprint('local', __name__, description='CRUD de locales y accesos.')
    
def set_local_settings(settings_data, local: LocalModel, local_settings: LocalSettingsModel = None):
    
    warnings = []
    
    def check_domain_smtp(smtp_user):
        user = smtp_user.split('@')[1]
        
        if not (user == settings_data['domain']):
            warnings.append(f"The domain of the email '{smtp_user}' does not match the domain of the local '{settings_data['domain']}'.")
    
    if settings_data:
    
        if settings_data['booking_timeout'] != -1 and settings_data['booking_timeout'] < MIN_TIMEOUT_CONFIRM_BOOKING:
            settings_data['booking_timeout'] = MIN_TIMEOUT_CONFIRM_BOOKING
            warnings.append(f'The minimum booking timeout is {MIN_TIMEOUT_CONFIRM_BOOKING} minutes.')
        
        smtp_settings = settings_data.pop('smtp_settings') if 'smtp_settings' in settings_data else None
    
        patch_smtp = False
        smtp_settings_models = []
                
        if local_settings:
            
            patch_smtp = True
            smtp_settings_models = list(local_settings.smtp_settings)
            
            for key, value in settings_data.items():
                setattr(local_settings, key, value)
            
        else:        
            local_settings = LocalSettingsModel(local_id = local.id, **settings_data)                
                        
        addAndFlush(local_settings)
                
        if smtp_settings is not None:
            
            priorities = []
            
            if len(smtp_settings) == 0:
                deleteAndFlush(*smtp_settings_models)
                smtp_settings_models = []
            
            for smtp_setting in smtp_settings:
                
                if patch_smtp:
                    name = smtp_setting['name']
                    
                    smtp_setting_model = None
                    
                    for smtp_model in smtp_settings_models:
                        if smtp_model.name == name:
                            smtp_setting_model = smtp_model
                            break
                        
                    if smtp_setting_model:
                        
                        for key, value in smtp_setting.items():
                            setattr(smtp_setting_model, key, value)
                        
                        for smtp_model in smtp_settings_models:
                            print("log")
                            print(smtp_model.id, smtp_setting_model.id, smtp_model.priority, smtp_setting_model.priority)
                            if smtp_model.id != smtp_setting_model.id and smtp_model.priority == smtp_setting_model.priority:
                                abort(409, message = f'The priority {smtp_setting_model.priority} is already in use.')
                        
                        addAndFlush(smtp_setting_model)
                        
                        continue
                    else:
                        schema = SmtpSettingsSchema()
                        keys = [ field_name for field_name, field_obj in schema.fields.items() if getattr(field_obj, 'required', False) ]
                        for k in keys:
                            if k not in smtp_setting:
                                abort(404, message = f"The smtp setting '{name}' does not exist. The field '{k}' is required.")
                    
                
                if 'max_send_per_month' in smtp_setting and 'reset_send_per_month' not in smtp_setting:
                    abort(400, message = f"The smtp setting '{smtp_setting['name']}' does not have a reset_send_per_month date.")
                    
                if 'max_send_per_day' in smtp_setting and 'reset_send_per_day' not in smtp_setting:
                    abort(400, message = f"The smtp setting '{smtp_setting['name']}' does not have a reset_send_per_month date.")
                
                if smtp_setting['priority'] in priorities:
                    abort(409, message = f'The priority {smtp_setting["priority"]} is already in use.')
                    
                priorities.append(smtp_setting['priority'])
                
                check_domain_smtp(smtp_setting['user'])
                                        
                smtp_model = SmtpSettingsModel(local_settings_id = local_settings.id, **smtp_setting)
                
                try:
                    addAndFlush(smtp_model)
                    smtp_settings_models.append(smtp_model)
                except IntegrityError as e:
                    traceback.print_exc()
                    rollback()
                    abort(409, message = f"The smtp name '{smtp_model.name}' is already in use.")
                
        if len(smtp_settings_models) == 0: warnings.append(f'The local has no smtp settings.')
        
        if patch_smtp:
            for smtp_model in smtp_settings_models:
                check_domain_smtp(smtp_model.user)    
                
        
        local_settings.smtp_settings = smtp_settings_models
                
    else: warnings.append(f'The local has no settings.')
    
    local.local_settings = local_settings if settings_data else None
    
    return warnings

def update_local(local_data, local_id, patch = False):
    local = LocalModel.query.get_or_404(local_id)
    
    try:
        
        settings_data = local_data.pop('local_settings') if 'local_settings' in local_data else None
        
        for key, value in local_data.items():
            setattr(local, key, value)
        
        if 'password' in local_data: local.password = pbkdf2_sha256.hash(local_data['password'])
        
        addAndFlush(local)
        
        settings_model = local.local_settings
        
        if settings_model and not patch:
            deleteAndFlush(settings_model)
            settings_model = None
        
        warnings = set_local_settings(settings_data, local, local_settings=settings_model)
        
        commit()
        
    except IntegrityError as e:
        traceback.print_exc()
        rollback()
        abort(409, message = 'The email is already in use.')
    except SQLAlchemyError as e:
        traceback.print_exc()
        rollback()
        abort(500, message = str(e) if DEBUG else 'Could not update the local.')
    
    return {"local": local, "warnings": warnings}
    
    
@blp.route('<string:local_id>')
class Local(MethodView):

    @blp.response(404, description='El local no existe.')
    @blp.response(200, PublicLocalSchema)
    def get(self, local_id):
        """
        Devuelve los datos públicos del local.
        """
        return LocalModel.query.get_or_404(local_id)
@blp.route('')
class Local(MethodView):

    @blp.response(404, description='El local no existe')
    @blp.response(200, LocalSchema)
    @jwt_required(refresh=True)
    def get(self):
        """
        Devuelve todos los datos del local identificado con el toquen de refresco.
        """
        return LocalModel.query.get_or_404(get_jwt_identity())
    
    
    @blp.arguments(LocalSchema)
    @blp.response(400, description='La zona horaria no es valida [campo location]. [Ex: Europe/Madrid].')
    @blp.response(409, description='El email ya está en uso o se repite el nivel de prioridad de los servidores smtp.')
    @blp.response(404, description='El token no existe.')
    @blp.response(403, description='No tienes permisos para crear un local.')
    @blp.response(401, description='Falta cabecera de autorización.')
    @blp.response(201, LocalTokensSchema)
    def post(self, local_data):
        F"""
        Crea un nuevo local.
        Si no se encuentra la contraseña, generará una nueva y la devolverá.
        Valor minimo de timeout_confirm_booking: {MIN_TIMEOUT_CONFIRM_BOOKING} minutos, o -1 para desactivar.
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

        try:
            
            settings_data = local_data.pop('local_settings') if 'local_settings' in local_data else None
            
            local = LocalModel(**local_data)
        
            local.password = pbkdf2_sha256.hash(local.password)
            
            addAndFlush(local)
            
            warnings = set_local_settings(settings_data, local)
            
            commit()
            
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
        
        return {'access_token': access_token, 'refresh_token': refresh_token, 'local': local, 'warnings': warnings}
    
    @blp.arguments(LocalSchema)
    @blp.response(409, description='El email ya está en uso o se repite el nivel de prioridad de los servidores smtp.')
    @blp.response(404, description='El local no existe.')
    @blp.response(200, LocalWarningSchema)
    @jwt_required(fresh=True)
    def put(self, local_data):
        f"""
        Actualiza los datos del local. Requiere token de acceso.
        Valor minimo de timeout_confirm_booking: {MIN_TIMEOUT_CONFIRM_BOOKING} minutos, o -1 para desactivar.
        """
        return update_local(local_data, get_jwt_identity())
        
    @blp.arguments(LocalPatchSchema)
    @blp.response(409, description='El email ya está en uso.')
    @blp.response(404, description='El local no existe.')
    @blp.response(200, LocalWarningSchema)
    @jwt_required(fresh=True)
    def patch(self, local_data):
        f"""
        Actualiza los datos indicados del local. Requiere token de acceso.
        Valor minimo de timeout_confirm_booking: {MIN_TIMEOUT_CONFIRM_BOOKING} minutos, o -1 para desactivar.
        """
        
        return update_local(local_data, get_jwt_identity(), patch=True)
        
    @blp.response(409, description='El email ya está en uso.')
    @blp.response(404, description='El local no existe.')
    @blp.response(204, description='Local eliminado.')
    @jwt_required(fresh=True)
    def delete(self):
        """
        Elimina completamente el local. Requiere token de acceso.
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
    @blp.response(401, description='Credenciales inválidas.')
    @blp.response(200, LocalTokensSchema)
    def post(self, login_data):
        """
        Inicia sesión en el sistema (email/password) y devuelve el token de acceso y refresco.
        """
        
        local = LocalModel.query.filter_by(email=login_data['email']).first()
        
        if not local or not pbkdf2_sha256.verify(login_data['password'], local.password):
            abort(401, message = 'Invalid credentials.')
            
        access_token, refresh_token = generateTokens(local.id, local.id, access_token=True, refresh_token=True)
            
        return {'access_token': access_token, 'refresh_token': refresh_token, 'local': local}
        
@blp.route('/logout')
class LocalLogout(MethodView):
    
    @jwt_required(refresh=True)
    @blp.response(204, description='Usuario deslogueado y token de refresco expirado.')
    def post(self):
        """
        Desloguea al usuario y expira el token de refresco.
        """
        tokenId = get_jwt().get('token')
        
        deleteAndCommit(SessionTokenModel.query.get(tokenId))
        
        return {}
    
@blp.route('/logout/all')
class LocalLogoutAll(MethodView):
    
    @jwt_required(refresh=True)
    @blp.response(204, description='Usuarios deslogueados y tokens de refresco expirados.')
    def post(self):
        """
        Desloguea a todos los usuarios usuario y expira todos los tokens de refresco.
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
        Actualiza el token de acceso. Expira el token de refresco y devuelve uno nuevo.
        """
        token = get_jwt()
        tokenId = token.get('token')
        
        token = SessionTokenModel.query.get_or_404(tokenId)
        
        if token.user_session.user != LOCAL_ROLE:
            abort(403, message = 'You are not allowed to refresh this token.')
        
        refresh_token = generateTokens(get_jwt_identity(), get_jwt_identity(), refresh_token=True)
        return {'refresh_token': refresh_token}