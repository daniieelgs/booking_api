from dotenv import load_dotenv
import os

load_dotenv()

DEFAULT_SECRET_JWT = '303333537232571254035672536717968198213'
DEFAULT_DATABASE_URI = 'sqlite:///data.db'
TEST_DATABASE_URI = 'sqlite:///data_test.db'
DEFAULT_API_PREFIX = 'api/v1'
DEFAULT_PASSWORD_SIZE = 8
DEFAULT_EXPRIE_TOKEN = 30
DEFAULT_EXPIRE_ACCESS = 5

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

DEFAULT_TIMEOUT_CONFIRM_BOOKING = 60

DEBUG = os.getenv('FLASK_DEBUG', 'False') == '1' or os.getenv('FLASK_DEBUG', 'False') == 1 or os.getenv('FLASK_DEBUG', 'False') == 'True'

DATABASE_NAME = os.getenv('DATABASE_NAME')
DATABASE_USER = os.getenv('DATABASE_USER')
DATABASE_PASS = os.getenv('DATABASE_PASS')
DATABASE_HOST = os.getenv('DATABASE_HOST')
DATABASE_PORT = os.getenv('DATABASE_PORT')

def getDatabaseUri():
    if DATABASE_NAME and DATABASE_USER and DATABASE_PASS and DATABASE_HOST and DATABASE_PORT:
        return f"mysql+pymysql://{DATABASE_USER}:{DATABASE_PASS}@{DATABASE_HOST}:{DATABASE_PORT}/{DATABASE_NAME}"
    else:
        return DEFAULT_DATABASE_URI

DATABASE_URI = os.getenv("DATABASE_URI", getDatabaseUri())

SECRET_JWT = os.getenv('SECRET_JWT', DEFAULT_SECRET_JWT)
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

TIMEOUT_CONFIRM_BOOKING = int(os.getenv('TIMEOUT_CONFURM_BOOKING', DEFAULT_TIMEOUT_CONFIRM_BOOKING))
ADMIN_ROLE = os.getenv('ADMIN_ROLE', DEFAULT_ADMIN_ROLE)
LOCAL_ROLE = os.getenv('LOCAL_ROLE', DEFAULT_LOCAL_ROLE)
USER_ROLE = os.getenv('USER_ROLE', DEFAULT_USER_ROLE)
