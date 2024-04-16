from dotenv import load_dotenv
import os

load_dotenv(verbose=True, override=True)

DEFAULT_SECRET_JWT = '303333537232571254035672536717968198213'
DEFAULT_CRYPTO_JWT = 'RkElcKTNxr_IfO-puTA7ZjiD9EisBbi0Zeo_Z00NrPA='
DEFAULT_CRYPTO_KEY_ENDS_EQUAL = 0
DEFAULT_DATABASE_URI = 'sqlite:///data.db'
TEST_DATABASE_URI = 'sqlite:///data_test.db'
DEFAULT_API_PREFIX = 'api/v1'
DEFAULT_PASSWORD_SIZE = 8
DEFAULT_EXPRIE_TOKEN = 30
DEFAULT_EXPIRE_ACCESS = 5

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

DEFAULT_KEYWORDS_PAGES = {
    "CONFIRMATION_LINK": "{confirmation_link}",
    "BOOKING_TOKEN": "{booking_token}",
    "CLIENT_NAME": "{client_name}",
    "LOCAL_NAME": "{local_name}",
    "DATE": "{date}",
    "TIME": "{time}",
    "SERVICE": "{service}",
    "COST": "{cost}",
    "ADDRESS-MAPS": "{address_maps}",
    "ADDRESS": "{address}",
    "PHONE_CONTACT": "{phone_contact}",
    "TIMEOUT_CONFIRM_BOOKING": "{timeout_confirm_booking}",
    "CANCEL_LINK": "{cancel_link}",
    "EMAIL_CONTACT": "{email_contact}",
    "WHATSAPP_LINK": "{whatsapp_link}",
    "WEBSITE": "{website}",
}

DEFAULT_TIMEOUT_CONFIRM_BOOKING = 60

DEFAULT_LOCATION_TIME = 'Europe/Madrid'

DEFAULT_MIN_TIMEOUT_CONFIRM_BOOKING = 5

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
KEYWORDS_PAGES = os.getenv('KEYWORDS_PAGES', None)
if KEYWORDS_PAGES:
    KEYWORDS_PAGES = {key.split('"')[1].strip(): value.split('"')[1].strip() for key, value in [keyword.split('":') for keyword in KEYWORDS_PAGES.split(',')]}
else: KEYWORDS_PAGES = DEFAULT_KEYWORDS_PAGES

ADMIN_IDENTITY = os.getenv('ADMIN_IDENTITY', DEFAULT_ADMIN_IDENTITY)
JWT_ALGORITHM = os.getenv('JWT_ALGORITHM', DEFAULT_JWT_ALGORITHM)

ADMIN_TOKEN = os.getenv('ADMIN_TOKEN')

CERT_SSL = os.getenv('CERT_SSL', None)
KEY_SSL = os.getenv('KEY_SSL', None)

