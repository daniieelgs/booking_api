from config import Config

from globals import DATABASE_URI, SECRET_JWT, API_PREFIX, API_TITLE, API_VERSION, OPENAPI_VERSION, OPENAPI_URL_PREFIX, OPENAPI_SWAGGER_UI_PATH, OPENAPI_SWAGGER_UI_URL, TIMEOUT_CONFIRM_BOOKING

class DefaultConfig(Config):
    
    def __init__(self) -> None:
        super().__init__(template_folder='templates', public_folder='public', public_folder_url='public', database_uri=DATABASE_URI, secret_jwt=SECRET_JWT, api_prefix=API_PREFIX, api_title=API_TITLE, api_version=API_VERSION, openapi_version=OPENAPI_VERSION, openapi_url_prefix=OPENAPI_URL_PREFIX, openapi_swagger_ui_path=OPENAPI_SWAGGER_UI_PATH, openapi_swagger_ui_url=OPENAPI_SWAGGER_UI_URL, waiter_booking_status=TIMEOUT_CONFIRM_BOOKING)