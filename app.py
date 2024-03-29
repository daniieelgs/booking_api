import os
import traceback
from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask_smorest import abort, Api
from flask_jwt_extended import JWTManager
from flask_migrate import Migrate
from sqlalchemy.exc import SQLAlchemyError

from flask_cors import CORS

import nltk
from config import Config

from db import db, deleteAndCommit
from default_config import DefaultConfig

from globals import DEBUG, CERT_SSL, KEY_SSL
from models.session_token import SessionTokenModel

from resources.local import blp as LocalBlueprint
from resources.work_group import blp as WorkGroupBlueprint
from resources.worker import blp as WorkerBlueprint
from resources.service import blp as ServiceBlueprint
from resources.timetable import blp as TimetableBlueprint
from resources.booking import blp as BookingBlueprint
from resources.images import blp as ImagesBlueprint
from resources.public_images import blp as PublicImagesBlueprint
from resources.admin import blp as AdminBlueprint

#TODO desarrollas sistema de LOGs

#TODO cambiar datetime.now() por hora actual del location del local
def create_app(config: Config = DefaultConfig()):

    TEMPLATE_FOLDER = config.template_folder
    PUBLIC_FOLDER_URL = config.public_folder_url

    load_dotenv()

    os.environ['PUBLIC_FOLDER'] = config.public_folder
    os.environ['PUBLIC_FOLDER_URL'] = PUBLIC_FOLDER_URL
    os.environ['TIMEOUT_CONFIRM_BOOKING'] = str(config.waiter_booking_status if config.waiter_booking_status else 0)
        
    load_dotenv()
            
    nltk.download('punkt')
    
    app = Flask(__name__, template_folder=TEMPLATE_FOLDER)
    CORS(app)
        
    app.debug = DEBUG
    app.jinja_env.auto_reload = DEBUG
    
    app.config['API_TITLE'] = config.api_title
    app.config['API_VERSION'] = config.api_version
    app.config['OPENAPI_VERSION'] = config.openapi_version
    app.config['OPENAPI_URL_PREFIX'] = config.openapi_url_prefix if DEBUG else None
    app.config['OPENAPI_SWAGGER_UI_PATH'] = config.openapi_swagger_ui_path if DEBUG else None
    app.config['OPENAPI_SWAGGER_UI_URL'] = config.openapi_swagger_ui_url

    ##BBDD
    app.config["SQLALCHEMY_DATABASE_URI"] = config.database_uri
    
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    
    app.config['JWT_SECRET_KEY'] = config.secret_jwt
    app.config['JWT_TOKEN_LOCATION'] = ['headers']
    app.config['JWT_HEADER_NAME'] = 'Authorization'
    app.config['JWT_HEADER_TYPE'] = 'Bearer'

    
        
    db.init_app(app)
    
    Migrate(app, db)
    
    api = Api(app)
    
    
    api.spec.components.security_scheme(
        'jwt', {'type': 'http', 'scheme': 'bearer', 'bearerFormat': 'JWT', 'x-bearerInfoFunc': 'app.decode_token'}
    )
    
    jwt = JWTManager(app)
    
    def getApiPrefix(url): return f"/{config.api_prefix}/{url}"
    
    ##JWT CHECK
    
    @jwt.token_in_blocklist_loader
    def check_if_token_in_blocklist(jwt_header, jwt_payload):
        
        try:
            tokenId = jwt_payload['token']
            jti = jwt_payload['jti']
            identity = jwt_payload['sub']
            
            try:
                session_token = SessionTokenModel.query.get(tokenId)
            except SQLAlchemyError as e:
                traceback.print_exc()
                abort(500, message = str(e) if DEBUG else 'Could not check the token.')
            
            if not session_token: return True
            
            return not (session_token.jti == jti and session_token.local_id == identity)
            
        except KeyError:
            return True
            
    ##JWT ERRORS
    
    @jwt.invalid_token_loader
    def invalid_token_callback(error):                
        return jsonify({"message": error, "error": "invalid_token"}), 401
    
    @jwt.needs_fresh_token_loader
    def token_not_fresh_callback(jwt_header, jwt_payload):
        return jsonify({"message": "The token is not fresh.", "error": "fresh_token_required"}), 401
    
    
    @jwt.expired_token_loader
    def expired_token_callback(jwt_header, jwt_payload):
        try:
            deleteAndCommit(SessionTokenModel.query.get(jwt_payload['token']))  
        except Exception as e:
            traceback.print_exc()
            abort(500, message = str(e) if DEBUG else 'Could not delete the session token.')
        return jsonify({"message": "The token has expired.", "error": "token_expired"}), 401
    
    @jwt.unauthorized_loader
    def missing_token_callback(error):
        headers = request.headers
        for header in headers:
            print(header)
        return jsonify({"message": error, "error": "token_unauthorized"}), 401

    @jwt.revoked_token_loader
    def revoked_token_callback(jwt_header, jwt_payload):
        return jsonify({"message": "The token has been revoked.", "error": "token_revoked"}), 401
    
    ##NotImplementedError
    
    @app.errorhandler(NotImplementedError)
    def handle_not_implemented_error(error):
        response = {
            "error_message": str(error),
            "code": 501,
            "status": "Not Implemented"
        }
        return jsonify(response), 501
    
    ##Routes
    
    api.register_blueprint(LocalBlueprint, url_prefix=getApiPrefix('local'))
    api.register_blueprint(WorkGroupBlueprint, url_prefix=getApiPrefix('work_group'))
    api.register_blueprint(WorkerBlueprint, url_prefix=getApiPrefix('worker'))
    api.register_blueprint(ServiceBlueprint, url_prefix=getApiPrefix('service'))
    api.register_blueprint(TimetableBlueprint, url_prefix=getApiPrefix('timetable'))
    api.register_blueprint(BookingBlueprint, url_prefix=getApiPrefix('booking'))
    api.register_blueprint(ImagesBlueprint, url_prefix=getApiPrefix('images'))
    api.register_blueprint(PublicImagesBlueprint, url_prefix=f'/{PUBLIC_FOLDER_URL}/images')
    api.register_blueprint(AdminBlueprint, url_prefix=getApiPrefix('admin'))
    
    ##Loal Routes
    
    # @app.get(f'/{PUBLIC_FOLDER_URL}/<string:resource>')
    # def public(resource):
    #     return app.send_static_file(resource)
                
    return app

app = create_app()

if __name__ == '__main__':
    
    cert_ssl = CERT_SSL
    key_ssl = KEY_SSL
    
    if cert_ssl and key_ssl:
        context = (cert_ssl, key_ssl)
        app.run(threaded=True, ssl_context=context)
    else:
        app.run(threaded=True)
    
    
    