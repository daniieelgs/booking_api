
from typing import Union


class Config:
    
    def __init__(self, template_folder: str, public_folder: str, public_folder_url: str, database_uri: str, secret_jwt: str, api_prefix: str, api_title: str, api_version: str, openapi_version: str, openapi_url_prefix: str, openapi_swagger_ui_path: str, openapi_swagger_ui_url: str, waiter_booking_status: Union[int, None], celery_broker_url: str, celery_result_backend: str, email_test_mode: bool, redis_test_mode: bool) -> None:
        self.template_folder = template_folder
        self.public_folder = public_folder
        self.public_folder_url = public_folder_url
        self.database_uri = database_uri
        self.secret_jwt = secret_jwt
        self.api_prefix = api_prefix
        self.api_title = api_title
        self.api_version = api_version
        self.openapi_version = openapi_version
        self.openapi_url_prefix = openapi_url_prefix
        self.openapi_swagger_ui_path = openapi_swagger_ui_path
        self.openapi_swagger_ui_url = openapi_swagger_ui_url
        self.waiter_booking_status = waiter_booking_status
        self.celery_broker_url = celery_broker_url
        self.celery_result_backend = celery_result_backend
        self.email_test_mode = email_test_mode
        self.redis_test_mode = redis_test_mode
        
    def config(selg, *args, **kwargs):
        pass
    
    def drop(self, *args, **kwargs):
        pass
