from config import Config

from globals import DATABASE_URI, SECRET_JWT, API_PREFIX

class DefaultConfig(Config):
    
    def __init__(self) -> None:
        super().__init__(template_folder='templates', public_folder='public', public_folder_url='public', database_uri=DATABASE_URI, secret_jwt=SECRET_JWT, api_prefix=API_PREFIX)