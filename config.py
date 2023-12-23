
class Config:
    
    def __init__(self, template_folder: str, public_folder: str, public_folder_url: str, database_uri: str, secret_jwt: str, api_prefix: str) -> None:
        self.template_folder = template_folder
        self.public_folder = public_folder
        self.public_folder_url = public_folder_url
        self.database_uri = database_uri
        self.secret_jwt = secret_jwt
        self.api_prefix = api_prefix
        