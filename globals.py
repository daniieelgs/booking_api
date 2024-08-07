from datetime import datetime
from enum import Enum
import json
from logging.handlers import TimedRotatingFileHandler
import socket
import threading
import traceback
import uuid
from dotenv import load_dotenv
import logging
import os

from flask import Request, Response

load_dotenv(verbose=True, override=True)

DEFAULT_SECRET_JWT = '303333537232571254035672536717968198213'
DEFAULT_CRYPTO_JWT = 'RkElcKTNxr_IfO-puTA7ZjiD9EisBbi0Zeo_Z00NrPA='
DEFAULT_CRYPTO_KEY_ENDS_EQUAL = 0
DEFAULT_DATABASE_URI = 'sqlite:///data.db'
DEFAULT_API_PREFIX = 'api/v1'
DEFAULT_PASSWORD_SIZE = 8
DEFAULT_EXPRIE_TOKEN = 30
DEFAULT_EXPIRE_ACCESS = 5

DEFAULT_CELERY_BROKER_URL = 'redis://localhost:6379/0'
DEFAULT_CELERY_RESULT_BACKEND = 'redis://localhost:6379/0'

DEFAULT_DAILY_HOUR = 3
DEFAULT_DAILY_MINUTE = 0

DEFAULT_REDIS_HOST = 'localhost'
DEFAULT_REDIS_PORT = 6379

DEFAULT_ADMIN_IDENTITY = '744656b1e8a24f998685134efabe2f3f'
DEFAULT_JWT_ALGORITHM = 'HS256'

DEFAULT_API_TITLE = 'Booking API'
DEFAULT_API_VERSION = 'v1'
DEFAULT_OPENAPI_VERSION = '3.0.3'
DEFAULT_OPENAPI_URL_PREFIX = '/'
DEFAULT_OPENAPI_SWAGGER_UI_PATH = '/swagger-ui'
DEFAULT_OPENAPI_SWAGGER_UI_URL = 'https://cdn.jsdelivr.net/npm/swagger-ui-dist/'

DEFAULT_PENDING_STATUS = 'P'
DEFAULT_CONFIRMED_STATUS = 'C'
DEFAULT_DONE_STATUS = 'D'
DEFAULT_CANCELLED_STATUS = 'X'

DEFAULT_ADMIN_ROLE = 'A'
DEFAULT_LOCAL_ROLE = 'L'
DEFAULT_USER_ROLE = 'U'

DEFAULT_WEEK_DAYS = 'MO-TU-WE-TH-FR-SA-SU'

WORKER_ID_GET = 'worker_id'
WORK_GROUP_ID_GET = 'work_group_id'
STATUS_LIST_GET = 'status'
DATE_GET = 'date'
DATETIME_INIT_GET = 'datetime_init'
DATETIME_END_GET = 'datetime_end'
FORMAT_GET = 'format'
DAYS_GET = 'days'
SESSION_GET = 'session'

DEFAULT_PARAM_FILE_NAME = 'file'
DEFAULT_IMAGE_TYPE_GALLERY = 'gallery'
DEFAULT_IMAGE_TYPE_LOGOS = 'logos'

DEFAULT_ALLOWED_EXTENSIONS = 'png,jpg,jpeg,html,xml'

DEFAULT_IMAGES_FOLDER = 'images'
DEFAULT_PAGES_FOLDER = 'pages'

DEFAULT_EMAIL_CONFIRMATION_PAGE = "email_confirmation.html"
DEFAULT_EMAIL_CONFIRMED_PAGE = "email_confirmed.html"
DEFAULT_EMAIL_CANCELLED_PAGE = "email_cancelled.html"
DEFAULT_EMAIL_UPDATED_PAGE = "email_updated.html"

DEFAULT_KEYWORDS_PAGES = {
    "CONFIRMATION_LINK": "{confirmation_link}",
    "CANCEL_LINK": "{cancel_link}",
    "UPDATE_LINK": "{update_link}",
    "BOOKING_TOKEN": "{booking_token}",
    "CLIENT_NAME": "{client_name}",
    "LOCAL_NAME": "{local_name}",
    "DATE": "{date}",
    "TIME": "{time}",
    "SERVICE": "{service}",
    "COST": "{cost}",
    "WORKER": "{worker}",
    "ADDRESS-MAPS": "{address_maps}",
    "ADDRESS": "{address}",
    "PHONE_CONTACT": "{phone_contact}",
    "TIMEOUT_CONFIRM_BOOKING": "{timeout_confirm_booking}",
    "EMAIL_CONTACT": "{email_contact}",
    "WHATSAPP_LINK": "{whatsapp_link}",
    "WEBSITE": "{website}",
    "COMMENT": "{comment}",
    "UUID_LOG": "{uuid_log}"
}

DEFAULT_TIMEOUT_CONFIRM_BOOKING = 60

DEFAULT_LOCATION_TIME = 'Europe/Madrid'

DEFAULT_MIN_TIMEOUT_CONFIRM_BOOKING = 5

DEFAULT_RETRY_SEND_EMAIL = 120

DEFAULT_MAX_TIMEOUT_WAIT_BOOKING = 5

#---- LOGGING CONFIG --------------

LOGGING_LEVELS = {
    'DEBUG': logging.DEBUG,
    'INFO': logging.INFO,
    'WARNING': logging.WARNING,
    'ERROR': logging.ERROR,
    'CRITICAL': logging.CRITICAL
}

DEFAULT_FILENAME_LOG = 'private/logs/app.log'
DEFAULT_ROTATING_LOG_WHEN = 'midnight'
DEFAULT_MAX_BYTES_LOG = 1024 * 1024 * 10 # 10MB
DEFAULT_BACKUP_COUNT_LOG = 3
DEFAULT_LOGGING_LEVEL = 'INFO'
DEFAULT_LOGGING_FORMAT = "[%(asctime)s] [%(levelname)s] - %(message)s"
DEFAULT_LOG_NAME = 'booking_app'

DEFAULT_DB_BACKUP_FOLDER = 'private/db/backup.sql'

#----------------------------------

#---- API BACKUP CONFIG ------------

DEFAULT_DB_BACKUP_ENDPOINT = '/upload/sql'
DEFAULT_LOG_BACKUP_ENDPOINT = '/upload/log'

#----------------------------------

#---- TEST CONFIG --------------

DEFAULT_TEST_DATABASE_URI = 'sqlite:///data_test.db'
DEFAULT_BOOKING_TIMEOUT_PERFORMANCE = 4
DEFAULT_API_PREFIX_PERFORMANCE = 'api/test'
DEFAULT_TEST_PERFORMANCE_FOLDER = 'tests/performance'
DEFAULT_EXPORT_DATABASE_PERFORMANCE_FILENAME = 'data_test_performance.sql'

#-------------------------------

DEBUG = os.getenv('FLASK_DEBUG', 'False') == '1' or os.getenv('FLASK_DEBUG', 'False') == 1 or os.getenv('FLASK_DEBUG', 'False') == 'True'

DATABASE_NAME = os.getenv('DATABASE_NAME')
DATABASE_USER = os.getenv('DATABASE_USER')
DATABASE_PASS = os.getenv('DATABASE_PASS')
DATABASE_HOST = os.getenv('DATABASE_HOST')
DATABASE_PORT = os.getenv('DATABASE_PORT')

DATABASE_USER_ROOT = os.getenv('DATABASE_USER_ROOT')
DATABASE_PASS_ROOT = os.getenv('DATABASE_PASS_ROOT')

def getDatabaseUri():
    if DATABASE_NAME and DATABASE_USER and DATABASE_PASS and DATABASE_HOST and DATABASE_PORT:
        return f"mysql+pymysql://{DATABASE_USER}:{DATABASE_PASS}@{DATABASE_HOST}:{DATABASE_PORT}/{DATABASE_NAME}"
    else:
        return DEFAULT_DATABASE_URI

DATABASE_URI = os.getenv("DATABASE_URI", getDatabaseUri())

CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', DEFAULT_CELERY_BROKER_URL)
CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', DEFAULT_CELERY_RESULT_BACKEND)

TIMEZONE = os.getenv('TIMEZONE', DEFAULT_LOCATION_TIME)

DAILY_HOUR = int(os.getenv('DAILY_HOUR', DEFAULT_DAILY_HOUR))
DAILY_MINUTE = int(os.getenv('DAILY_MINUTE', DEFAULT_DAILY_MINUTE))

REDIS_HOST = os.getenv('REDIS_HOST', DEFAULT_REDIS_HOST)
REDIS_PORT = os.getenv('REDIS_PORT', DEFAULT_REDIS_PORT)

SECRET_JWT = os.getenv('SECRET_JWT', DEFAULT_SECRET_JWT)
CRYPTO_KEY = os.getenv('CRYPTO_KEY', DEFAULT_CRYPTO_JWT)
CRYPTO_KEY_ENDS_EQUAL = int(os.getenv('CRYPTO_KEY_ENDS_EQUAL', DEFAULT_CRYPTO_KEY_ENDS_EQUAL))
CRYPTO_KEY = CRYPTO_KEY + ('=' * CRYPTO_KEY_ENDS_EQUAL)
API_PREFIX = os.getenv('API_PREFIX', DEFAULT_API_PREFIX)

PASSWORD_SIZE = int(os.getenv('PASSWORD_SIZE', DEFAULT_PASSWORD_SIZE))
EXPIRE_TOKEN = int(os.getenv('EXPIRE_TOKEN', DEFAULT_EXPRIE_TOKEN))
EXPIRE_ACCESS = int(os.getenv('EXPIRE_ACCESS', DEFAULT_EXPIRE_ACCESS))

API_TITLE = os.getenv('API_TITLE', DEFAULT_API_TITLE)
API_VERSION = os.getenv('API_VERSION', DEFAULT_API_VERSION)
OPENAPI_VERSION = os.getenv('OPENAPI_VERSION', DEFAULT_OPENAPI_VERSION)
OPENAPI_URL_PREFIX = os.getenv('OPENAPI_URL_PREFIX', DEFAULT_OPENAPI_URL_PREFIX)
OPENAPI_SWAGGER_UI_PATH = os.getenv('OPENAPI_SWAGGER_UI_PATH', DEFAULT_OPENAPI_SWAGGER_UI_PATH)
OPENAPI_SWAGGER_UI_URL = os.getenv('OPENAPI_SWAGGER_UI_URL', DEFAULT_OPENAPI_SWAGGER_UI_URL)

PENDING_STATUS = os.getenv('PENDING_STATUS', DEFAULT_PENDING_STATUS)
CONFIRMED_STATUS = os.getenv('CONFIRMED_STATUS', DEFAULT_CONFIRMED_STATUS)
DONE_STATUS = os.getenv('DONE_STATUS', DEFAULT_DONE_STATUS)
CANCELLED_STATUS = os.getenv('CANCELLED_STATUS', DEFAULT_CANCELLED_STATUS)
WEEK_DAYS = os.getenv('WEEK_DAYS', DEFAULT_WEEK_DAYS).split('-')

TIMEOUT_CONFIRM_BOOKING = int(os.getenv('TIMEOUT_CONFIRM_BOOKING', DEFAULT_TIMEOUT_CONFIRM_BOOKING))
if TIMEOUT_CONFIRM_BOOKING == -1:
    TIMEOUT_CONFIRM_BOOKING = None
MIN_TIMEOUT_CONFIRM_BOOKING = int(os.getenv('MIN_TIMEOUT_BOOKING', DEFAULT_MIN_TIMEOUT_CONFIRM_BOOKING))
ADMIN_ROLE = os.getenv('ADMIN_ROLE', DEFAULT_ADMIN_ROLE)
LOCAL_ROLE = os.getenv('LOCAL_ROLE', DEFAULT_LOCAL_ROLE)
USER_ROLE = os.getenv('USER_ROLE', DEFAULT_USER_ROLE)

PARAM_FILE_NAME = os.getenv('PARAM_FILE_NAME', DEFAULT_PARAM_FILE_NAME)
IMAGE_TYPE_GALLERY = os.getenv('IMAGE_TYPE_GALLERY', DEFAULT_IMAGE_TYPE_GALLERY)
IMAGE_TYPE_LOGOS = os.getenv('IMAGE_TYPE_LOGOS', DEFAULT_IMAGE_TYPE_LOGOS)
ALLOWED_EXTENSIONS = os.getenv('ALLOWED_EXTENSIONS', DEFAULT_ALLOWED_EXTENSIONS).split(',')

IMAGES_FOLDER = os.getenv('IMAGES_FOLDER', DEFAULT_IMAGES_FOLDER)
PAGES_FOLDER = os.getenv('PAGES_FOLDER', DEFAULT_PAGES_FOLDER)

EMAIL_CONFIRMATION_PAGE = os.getenv('EMAIL_CONFIRMATION_PAGE', DEFAULT_EMAIL_CONFIRMATION_PAGE)
EMAIL_CONFIRMED_PAGE = os.getenv('EMAIL_CONFIRMED_PAGE', DEFAULT_EMAIL_CONFIRMED_PAGE)
EMAIL_CANCELLED_PAGE = os.getenv('EMAIL_CANCELLED_PAGE', DEFAULT_EMAIL_CANCELLED_PAGE)
EMAIL_UPDATED_PAGE = os.getenv('EMAIL_UPDATED_PAGE', DEFAULT_EMAIL_UPDATED_PAGE)

KEYWORDS_PAGES = os.getenv('KEYWORDS_PAGES', None)
if KEYWORDS_PAGES:
    KEYWORDS_PAGES = {key.split('"')[1].strip(): value.split('"')[1].strip() for key, value in [keyword.split('":') for keyword in KEYWORDS_PAGES.split(',')]}
else: KEYWORDS_PAGES = DEFAULT_KEYWORDS_PAGES

ADMIN_IDENTITY = os.getenv('ADMIN_IDENTITY', DEFAULT_ADMIN_IDENTITY)
JWT_ALGORITHM = os.getenv('JWT_ALGORITHM', DEFAULT_JWT_ALGORITHM)

ADMIN_TOKEN = os.getenv('ADMIN_TOKEN')

RETRY_SEND_EMAIL = int(os.getenv('RETRY_SEND_EMAIL', DEFAULT_RETRY_SEND_EMAIL))

MAX_TIMEOUT_WAIT_BOOKING = int(os.getenv('MAX_TIMEOUT_WAIT_BOOKING', DEFAULT_MAX_TIMEOUT_WAIT_BOOKING))

CERT_SSL = os.getenv('CERT_SSL', None)
KEY_SSL = os.getenv('KEY_SSL', None)

FQDN_CACHE = None

def update_fqdn_cache():
    global FQDN_CACHE
    FQDN_CACHE = socket.getfqdn()

def get_fqdn_cache():
    global FQDN_CACHE
    if not FQDN_CACHE:
        update_fqdn_cache()
    return FQDN_CACHE

#---- LOGGING CONFIG --------------

MAX_BYTES_LOG = int(os.getenv('MAX_BYTES_LOG', DEFAULT_MAX_BYTES_LOG))
BACKUP_COUNT_LOG = int(os.getenv('BACKUP_COUNT_LOG', DEFAULT_BACKUP_COUNT_LOG))

FILENAME_LOG = os.getenv('FILENAME_LOG', DEFAULT_FILENAME_LOG)
ROTATING_LOG_WHEN = os.getenv('ROTATING_LOG_WHEN', DEFAULT_ROTATING_LOG_WHEN)

LOGGING_FORMAT = os.getenv('LOGGING_FORMAT', DEFAULT_LOGGING_FORMAT)

LOG_NAME = os.getenv('LOG_NAME', DEFAULT_LOG_NAME)

DB_BACKUP_FOLDER = os.getenv('DB_BACKUP_FOLDER', DEFAULT_DB_BACKUP_FOLDER)

_LOGGING_LEVEL = os.getenv('LOGGING_LEVEL', DEFAULT_LOGGING_LEVEL)
LOGGING_LEVEL = LOGGING_LEVELS[_LOGGING_LEVEL] if _LOGGING_LEVEL in LOGGING_LEVELS else LOGGING_LEVELS[DEFAULT_LOGGING_LEVEL]

#---------------------------------

#---- API BACKUP CONFIG ------------

DB_BACKUP_ENDPOINT = os.getenv('DB_BACKUP_ENDPOINT', DEFAULT_DB_BACKUP_ENDPOINT)
LOG_BACKUP_ENDPOINT = os.getenv('LOG_BACKUP_ENDPOINT', DEFAULT_LOG_BACKUP_ENDPOINT)

USERNAME_BACKUP_API = os.getenv('USERNAME_BACKUP_API')
PASSWORD_BACKUP_API = os.getenv('PASSWORD_BACKUP_API')

HOST_BACKUP_API = os.getenv('HOST_BACKUP_API')

#----------------------------------

#---- TEST CONFIG --------------

DEFAULT_DATABASE_NAME_PERFORMANCE = 'data_test_performance'
DATABASE_NAME_PERFORMANCE = os.getenv('DATABASE_NAME_PERFORMANCE', DEFAULT_DATABASE_NAME_PERFORMANCE)    
DEFAULT_TEST_PERFORMANCE_DATABASE_URI = f'sqlite:///{DATABASE_NAME_PERFORMANCE}.db'
DEFAULT_OVERWRITE_DATABASE_PERFORMANCE = True
TEST_PERFORMANCE = os.getenv('TEST_PERFORMANCE', 'False') == '1' or os.getenv('TEST_PERFORMANCE', 'False') == 1 or os.getenv('TEST_PERFORMANCE', 'False') == 'True'
API_PREFIX_PERFORMANCE = os.getenv('API_PREFIX_PERFORMANCE', DEFAULT_API_PREFIX_PERFORMANCE)
TEST_PERFORMANCE_FOLDER = os.getenv('TEST_PERFORMANCE_FOLDER', DEFAULT_TEST_PERFORMANCE_FOLDER)
EXPORT_DATABASE_PERFORMANCE_FILENAME = os.getenv('EXPORT_DATABASE_PERFORMANCE_FILENAME', DEFAULT_EXPORT_DATABASE_PERFORMANCE_FILENAME)
    
def getDatabaseUriPerformance():
    if DATABASE_USER and DATABASE_PASS and DATABASE_HOST and DATABASE_PORT:
        return f"mysql+pymysql://{DATABASE_USER}:{DATABASE_PASS}@{DATABASE_HOST}:{DATABASE_PORT}/{DATABASE_NAME_PERFORMANCE}"
    else:
        return DEFAULT_DATABASE_NAME_PERFORMANCE
    
TEST_DATABASE_URI = os.getenv("TEST_DATABASE_URI", DEFAULT_TEST_DATABASE_URI)
TEST_PERFORMANCE_DATABASE_URI = os.getenv("TEST_PERFORMANCE_DATABASE_URI", getDatabaseUriPerformance())
OVERWRITE_DATABASE_PERFORMANCE = str(os.getenv("OVERWRITE_DATABASE_PERFORMANCE", DEFAULT_OVERWRITE_DATABASE_PERFORMANCE))
OVERWRITE_DATABASE_PERFORMANCE = OVERWRITE_DATABASE_PERFORMANCE == 'True' or OVERWRITE_DATABASE_PERFORMANCE == '1'
BOOKING_TIMEOUT_PERFORMANCE = int(os.getenv('BOOKING_TIMEOUT_PERFORMANCE', DEFAULT_BOOKING_TIMEOUT_PERFORMANCE))


def is_email_test_mode():
    if DEBUG:
        load_dotenv()
        
        email_test_mode = os.getenv('EMAIL_TEST_MODE', 'False')
        
        return email_test_mode == 'True' or email_test_mode == '1'
    
def is_redis_test_mode():
    if DEBUG:
        load_dotenv()
        
        redis_test_mode = os.getenv('REDIS_TEST_MODE', 'False')
        
        return redis_test_mode == 'True' or redis_test_mode == '1'
    
#-------------------------------

app = None

logger = None

def setApp(_app):
    global app
    app = _app
    
def getApp():
    global app
    return app

def setLogger(_logger = None):
    global logger
    
    if not _logger:
        _logger = logging.getLogger(LOG_NAME)
        _logger.setLevel(LOGGING_LEVEL)
        
        handler = TimedRotatingFileHandler(FILENAME_LOG, when=ROTATING_LOG_WHEN, interval=1, backupCount=BACKUP_COUNT_LOG)
        formatter = logging.Formatter(LOGGING_FORMAT)
        handler.setFormatter(formatter)
        _logger.addHandler(handler)
    
    logger = _logger
    
def getLogger():
    global logger
    return logger

cache_log = {}

def log_parallel(logs:dict):
    logger = getLogger()
    
    for log in logs:
        
        level = log.get('level', 'INFO')
        message = log.get('message', '')
        
        error = log.get('error', None)
        
        level = level.upper()
        
        if logger:
            if level == 'DEBUG':
                logger.debug(message)
            elif level == 'INFO':
                logger.info(message)
            elif level == 'WARNING':
                logger.warning(message)
                if error: logger.warning(str(error))
            elif level == 'ERROR':
                logger.error(message)
                if error:
                    try:
                        logger.error(error, exc_info=True, stack_info=True)
                    except Exception as e:
                        logger.error(str(error))
            
        # time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        

    

def log(message, level='INFO', uuid=uuid.uuid4().hex, request:Request = None, response:Response = None, error:Exception=None, save_cache=False):
        
    try:
        if request and response:
            response_data = {
                'uuid': uuid,
                'headers': {
                    'Content-Length': response.content_length,
                    'Content-Type': request.content_type,
                    'Host': request.host,
                },
                'data': response.json if response.is_json else response.get_data(as_text=True)
            }
            
            message = f'RESPONSE | < [{request.remote_addr}] - \'[{request.method}] {request.path}\' => {response.status_code} - {message}:\n\tDATA : {json.dumps(response_data)} >'

        elif request:
            
            data_info = {
                'headers': {
                    'Authorization': request.headers.get('Authorization', 'None'),
                    'Content-Type': request.content_type,
                    'Host': request.host,
                },    
                'json': request.json if request.is_json else {},
                'form': request.form,
                'files': request.files,
                'args': request.args
            }
            
            json_data = {
                'uuid': uuid,
                'data': data_info
            }
            
            message = f'REQUEST | < [{request.remote_addr}] - \'[{request.method}] {request.path}\' - {message}:\n\tDATA : {json.dumps(json_data)} >'

        time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        if uuid:
            message = f"[{uuid}]: {message}"
            
            print(f"[{time}] [{level}] - {message}")
            
            log_uuid = {"level": level, "message": message, "error": str(error) if error else None, "time": datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            
            if uuid not in cache_log:
                cache_log[uuid] = [log_uuid]
            else:
                cache_log[uuid].append(log_uuid)
            
            if not save_cache: return uuid
                    
        logs = cache_log.get(uuid, [])
        
        thread = threading.Thread(target=log_parallel, args=(logs,))
        
        thread.start()
        
        cache_log.pop(uuid, None)
    
    except Exception as e:
        print(f"Error logging: {e}")
        traceback.print_exc()
    
    return uuid


class EmailType():
    CONFIRM_EMAIL = 0
    CONFIRMED_EMAIL = 1
    CANCELLED_EMAIL = 2
    UPDATED_EMAIL = 3