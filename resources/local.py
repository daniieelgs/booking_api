
import traceback
from flask import request

from flask_jwt_extended import get_jwt, get_jwt_identity, jwt_required
from pytz import UnknownTimeZoneError
from helpers.DatetimeHelper import now
from helpers.LoggingMiddleware import log_route
from helpers.error.SecurityError.AdminTokenIdentityException import AdminTokenIdentityException
from helpers.error.SecurityError.AdminTokenRoleException import AdminTokenRoleException
from helpers.error.SecurityError.NoTokenProvidedException import NoTokenProvidedException
from helpers.error.SecurityError.TokenNotFound import TokenNotFoundException
from helpers.path import createPathFromLocal, removePath
from helpers.security import check_admin_request, decodeJWT, generatePassword, generateTokens, generateUUID, logOutAll
from flask_smorest import Blueprint, abort
from flask.views import MethodView
from sqlalchemy.exc import SQLAlchemyError, IntegrityError

from passlib.hash import pbkdf2_sha256

from db import addAndFlush, commit, deleteAndCommit, addAndCommit, deleteAndFlush, rollback

from globals import ADMIN_IDENTITY, ADMIN_ROLE, DEBUG, LOCAL_ROLE, MIN_TIMEOUT_CONFIRM_BOOKING, TIMEOUT_CONFIRM_BOOKING, log
from models.local_settings import LocalSettingsModel
from models.session_token import SessionTokenModel
from models.smtp_settings import SmtpSettingsModel
from schema import LocalPatchSchema, LocalSchema, LocalTokensSchema, LocalWarningSchema, LoginLocalSchema, PublicLocalSchema, SmtpSettingsSchema

from models import LocalModel

blp = Blueprint('local', __name__, description='CRUD de locales y accesos.')
    
def set_local_settings(settings_data, local: LocalModel, local_settings: LocalSettingsModel = None, _uuid = None):
    
    warnings = []
    
    def check_domain_smtp(smtp_mail, domain = settings_data['domain'] if settings_data and 'domain' in settings_data else (local_settings.domain if local_settings else "")):
        user = smtp_mail.split('@')[1]
        
        if not (user == domain):
            log(f"The domain of the email '{smtp_mail}' does not match the domain of the local '{domain}'.", uuid=_uuid)
            warnings.append(f"The domain of the email '{smtp_mail}' does not match the domain of the local '{domain}'.")
        
    if settings_data:
    
        log('Setting local settings', uuid=_uuid)
    
        if 'booking_timeout' in settings_data and settings_data['booking_timeout'] != None and settings_data['booking_timeout'] < MIN_TIMEOUT_CONFIRM_BOOKING:
            if settings_data['booking_timeout'] < 0:
                settings_data['booking_timeout'] = None
                log('Booking timeout disabled', uuid=_uuid)
                warnings.append(f'The booking timeout is disabled.')
            else:
                settings_data['booking_timeout'] = MIN_TIMEOUT_CONFIRM_BOOKING
                log('Booking timeout set to minimum', uuid=_uuid)
                warnings.append(f'The minimum booking timeout is {MIN_TIMEOUT_CONFIRM_BOOKING} minutes.')
        
        smtp_settings = settings_data.pop('smtp_settings') if 'smtp_settings' in settings_data else None
    
        patch_smtp = False
        smtp_settings_models = []
                
        if local_settings:
            
            log('Patching local settings', uuid=_uuid)
            patch_smtp = True
            smtp_settings_models = list(local_settings.smtp_settings)
            
            for key, value in settings_data.items():
                setattr(local_settings, key, value)
            
        else:
            log('Creating local settings', uuid=_uuid)        
            local_settings = LocalSettingsModel(local_id = local.id, **settings_data)                
                        
        addAndFlush(local_settings)
                
        if smtp_settings is not None:
            
            log('Setting smtp settings', uuid=_uuid)
            
            priorities = []
            names = []
            
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
                        
                        if 'remove' in smtp_setting and smtp_setting['remove']:
                            deleteAndFlush(smtp_setting_model)
                            smtp_settings_models.remove(smtp_setting_model)
                            continue
                        
                        if 'new_name' in smtp_setting:
                            smtp_setting['name'] = smtp_setting['new_name']
                            smtp_setting.pop('new_name')
                        
                        for key, value in smtp_setting.items():
                            setattr(smtp_setting_model, key, value)
                        
                        for smtp_model in smtp_settings_models:
                            if smtp_model.id != smtp_setting_model.id and smtp_model.priority == smtp_setting_model.priority:
                                rollback()
                                log(f'Priority "{smtp_setting_model.priority}" conflict: {smtp_model.id} - {smtp_setting_model.id}', uuid=_uuid)
                                abort(409, message = f'The priority {smtp_setting_model.priority} is already in use.')
                                
                            if smtp_model.id != smtp_setting_model.id and smtp_model.name == smtp_setting_model.name:
                                rollback()
                                log(f'Name "{smtp_setting_model.name}" conflict: {smtp_model.id} - {smtp_setting_model.id}', uuid=_uuid)
                                abort(409, message = f'The name {smtp_setting_model.name} is already in use.')
                        
                        addAndFlush(smtp_setting_model)
                        
                        continue
                    else:
                        schema = SmtpSettingsSchema()
                        keys = [ field_name for field_name, field_obj in schema.fields.items() if getattr(field_obj, 'required', False) ]
                        for k in keys:
                            if k not in smtp_setting:
                                rollback()
                                log(f'The smtp setting "{name}" does not have the field "{k}"', uuid=_uuid)
                                abort(404, message = f"The smtp setting '{name}' does not exist. The field '{k}' is required.")
                
                if 'max_send_per_month' in smtp_setting and 'reset_send_per_month' not in smtp_setting:
                    rollback()
                    log(f'Missing reset_send_per_month in {smtp_setting["name"]}', uuid=_uuid)
                    abort(400, message = f"The smtp setting '{smtp_setting['name']}' does not have a reset_send_per_month date.")
                    
                if 'max_send_per_day' in smtp_setting and 'reset_send_per_day' not in smtp_setting:
                    rollback()
                    log(f'Missing reset_send_per_day in {smtp_setting["name"]}', uuid=_uuid)
                    abort(400, message = f"The smtp setting '{smtp_setting['name']}' does not have a reset_send_per_month date.")
                
                if smtp_setting['priority'] in priorities:
                    rollback()
                    log(f'Priority "{smtp_setting["priority"]}" conflict', uuid=_uuid)
                    abort(409, message = f'The priority {smtp_setting["priority"]} is already in use.')
                    
                if smtp_setting['name'] in names:
                    rollback()
                    log(f'Name "{smtp_setting["name"]}" conflict', uuid=_uuid)
                    abort(409, message = f'The name {smtp_setting["name"]} is already in use.')
                    
                priorities.append(smtp_setting['priority'])
                names.append(smtp_setting['name'])
                
                check_domain_smtp(smtp_setting['mail'])
                                        
                smtp_model = SmtpSettingsModel(local_settings_id = local_settings.id, **smtp_setting)
                
                try:
                    addAndFlush(smtp_model)
                    smtp_settings_models.append(smtp_model)
                except IntegrityError as e:
                    traceback.print_exc()
                    rollback()
                    raise e
                
        if len(smtp_settings_models) == 0:
            log('No smtp settings', uuid=_uuid)
            warnings.append(f'The local has no smtp settings.')
        
        if patch_smtp:
            for smtp_model in smtp_settings_models:
                check_domain_smtp(smtp_model.mail)    
                
        
        local_settings.smtp_settings = smtp_settings_models
                               
    else:
        log('No settings', uuid=_uuid)
        warnings.append(f'The local has no settings.')
    
    local.local_settings = local_settings if settings_data else None
    
    return warnings

def update_local(local_data, local_id, patch = False, _uuid = None):
    local = LocalModel.query.get_or_404(local_id)
    
    log(f'Updating local {local_id}', uuid=_uuid)
    
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
        elif settings_model and patch and settings_data and 'booking_timeout' not in settings_data:
            settings_data['booking_timeout'] = local.local_settings.booking_timeout
        elif not settings_data and settings_model and patch:
            settings_data = settings_model.__dict__
        
        warnings = set_local_settings(settings_data, local, local_settings=settings_model, _uuid=_uuid)
        
        if len(warnings) > 0: log('Warnings: [' + ' - '.join(warnings) + ']', uuid=_uuid)
        else: log('No warnings', uuid=_uuid)
        
        commit()
        
        log('Local updated', uuid=_uuid)
        
    except IntegrityError as e:
        traceback.print_exc()
        rollback()
        log('Integrity error', uuid=_uuid, error=e, level='WARNING')
        abort(409, message = 'The email is already in use.')
    except SQLAlchemyError as e:
        traceback.print_exc()
        rollback()
        log('SQLAlchemy error', uuid=_uuid, error=e, level='ERROR')
        abort(500, message = str(e) if DEBUG else 'Could not update the local.')
    
    return {"local": local, "warnings": warnings}
    
    
@blp.route('<string:local_id>')
class Local(MethodView):

    @log_route
    @blp.response(404, description='El local no existe.')
    @blp.response(200, PublicLocalSchema)
    def get(self, local_id, _uuid = None):
        """
        Devuelve los datos públicos del local.
        """
        return LocalModel.query.get_or_404(local_id)
    
    @log_route
    @blp.response(404, description='El token no existe.')
    @blp.response(403, description='No tienes permisos para eliminar un local.')
    @blp.response(401, description='Falta cabecera de autorización.')
    @blp.response(204, description='Local eliminado.')
    def delete(self, local_id, _uuid = None): #TODO eliminar reservas, trabajdores, etc.
        """
        Elimina completamente el local. Requiere token de acceso.
        """
        
        try:
            id, identity = check_admin_request(request)
        except NoTokenProvidedException:
            abort(401, message = 'Missing Authorization Header.')
        except (AdminTokenIdentityException, AdminTokenRoleException) as e:
            abort(403, message = 'You are not allowed to create a local.')
        except TokenNotFoundException:
            abort(404, message = 'The token does not exist.')
        
        log(f'Token decoded. Removing local. [Identiy={identity}. Id={id}]', uuid=_uuid)
        
        local = LocalModel.query.get_or_404(local_id)
        
        try:
            deleteAndCommit(local)
            log('Local removed', uuid=_uuid)
            p = removePath(local_id)
            log(f"'{p}' removed.", uuid=_uuid)
        except Exception as e:
            traceback.print_exc()
            rollback()
            log('Error removing local.', uuid=_uuid, error=e, level='ERROR')
            abort(500, message = str(e) if DEBUG else 'Could not delete the local.')
        
        return {}
@blp.route('')
class Local(MethodView):

    @log_route
    @blp.response(404, description='El local no existe')
    @blp.response(200, LocalSchema)
    @jwt_required(refresh=True)
    def get(self, _uuid = None):
        """
        Devuelve todos los datos del local identificado con el toquen de refresco.
        """
        return LocalModel.query.get_or_404(get_jwt_identity())
    
    
    @log_route
    @blp.arguments(LocalSchema)
    @blp.response(400, description='La zona horaria no es valida [campo location]. [Ex: Europe/Madrid].')
    @blp.response(409, description='El email ya está en uso o se repite el nivel de prioridad de los servidores smtp.')
    @blp.response(404, description='El token no existe.')
    @blp.response(403, description='No tienes permisos para crear un local.')
    @blp.response(401, description='Falta cabecera de autorización.')
    @blp.response(201, LocalTokensSchema)
    def post(self, local_data, _uuid = None):
        f"""
        Crea un nuevo local.
        Si no se encuentra la contraseña, generará una nueva y la devolverá.
        Valor minimo de timeout_confirm_booking: {MIN_TIMEOUT_CONFIRM_BOOKING} minutos, o -1 para desactivar.
        """
        
        try:
            id, identity = check_admin_request(request)
        except NoTokenProvidedException:
            abort(401, message = 'Missing Authorization Header.')
        except (AdminTokenIdentityException, AdminTokenRoleException) as e:
            abort(403, message = 'You are not allowed to create a local.')
        except TokenNotFoundException:
            abort(404, message = 'The token does not exist.')
        
        log(f'Token decoded. Creating local. [Identiy={identity}. Id={id}]', uuid=_uuid)
        
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
            
            log('Local created. Creating path', uuid=_uuid)
            createPathFromLocal(local.id, _uuid)
            access_token, refresh_token = generateTokens(local.id, local.id, access_token=True, refresh_token=True)
        except IntegrityError as e:
            traceback.print_exc()
            rollback()
            log('Integrity error', uuid=_uuid, error=e, level='WARNING')
            abort(409, message = 'The email is already in use.')
        except SQLAlchemyError as e:
            traceback.print_exc()
            rollback()
            log('SQLAlchemy error', uuid=_uuid, error=e, level='ERROR')
            abort(500, message = str(e) if DEBUG else 'Could not create the local.')

        if show_password: local.password_generated = local_data['password']
                
        return {'access_token': access_token, 'refresh_token': refresh_token, 'local': local, 'warnings': warnings}
    
    @log_route
    @blp.arguments(LocalSchema)
    @blp.response(409, description='El email ya está en uso o se repite el nivel de prioridad de los servidores smtp.')
    @blp.response(404, description='El local no existe.')
    @blp.response(200, LocalWarningSchema)
    @jwt_required(fresh=True)
    def put(self, local_data, _uuid = None):
        f"""
        Actualiza los datos del local. Requiere token de acceso.
        Valor minimo de timeout_confirm_booking: {MIN_TIMEOUT_CONFIRM_BOOKING} minutos, o -1 para desactivar.
        """
        return update_local(local_data, get_jwt_identity(), _uuid=_uuid)
        
    @log_route
    @blp.arguments(LocalPatchSchema)
    @blp.response(409, description='El email ya está en uso.')
    @blp.response(404, description='El local no existe.')
    @blp.response(200, LocalWarningSchema)
    @jwt_required(fresh=True)
    def patch(self, local_data, _uuid = None):
        f"""
        Actualiza los datos indicados del local. Requiere token de acceso.
        Valor minimo de timeout_confirm_booking: {MIN_TIMEOUT_CONFIRM_BOOKING} minutos, o -1 para desactivar.
        """
        log('Patching local', uuid=_uuid)
        return update_local(local_data, get_jwt_identity(), patch=True, _uuid=_uuid)
        
    
@blp.route('/login')
class AccessLocal(MethodView):
    
    @blp.arguments(LoginLocalSchema)
    @blp.response(401, description='Credenciales inválidas.')
    @blp.response(200, LocalTokensSchema)
    def post(self, login_data, _uuid = None):
        """
        Inicia sesión en el sistema (email/password) y devuelve el token de acceso y refresco.
        """
                
        local = LocalModel.query.filter_by(email=login_data['email']).first()
                
        if not local or not pbkdf2_sha256.verify(login_data['password'], local.password):
            abort(401, message = 'Invalid credentials.')
        
        log(f'Logging in local "{local.id}". [{login_data["email"]}:{login_data["email"]}]', uuid=_uuid)
            
        access_token, refresh_token = generateTokens(local.id, local.id, access_token=True, refresh_token=True)
            
        return {'access_token': access_token, 'refresh_token': refresh_token, 'local': local}
        
@blp.route('/logout')
class LocalLogout(MethodView):
    
    @log_route
    @jwt_required(refresh=True)
    @blp.response(204, description='Usuario deslogueado y token de refresco expirado.')
    def post(self, _uuid = None):
        """
        Desloguea al usuario y expira el token de refresco.
        """
        tokenId = get_jwt().get('token')
        
        deleteAndCommit(SessionTokenModel.query.get(tokenId))
        
        return {}
    
@blp.route('/logout/all')
class LocalLogoutAll(MethodView):
    
    @log_route
    @jwt_required(refresh=True)
    @blp.response(204, description='Usuarios deslogueados y tokens de refresco expirados.')
    def post(self, _uuid = None):
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
    
    @log_route
    @jwt_required(refresh=True)
    @blp.response(200, LocalTokensSchema)
    def post(self, _uuid = None):
        """
        Actualiza el token de acceso. Expira el token de refresco y devuelve uno nuevo.
        """
        token = get_jwt()
        tokenId = token.get('token')
        
        token = SessionTokenModel.query.get_or_404(tokenId)
        
        if token.user_session.user != LOCAL_ROLE:
            log(f'Token {tokenId} is not a local token.', uuid=_uuid)
            abort(403, message = 'You are not allowed to refresh this token.')
        
        refresh_token = generateTokens(get_jwt_identity(), get_jwt_identity(), refresh_token=True)
        return {'refresh_token': refresh_token}