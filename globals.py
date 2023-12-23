from dotenv import load_dotenv
import os

load_dotenv()

DEFAULT_SECRET_JWT = '303333537232571254035672536717968198213'
DEFAULT_DATABASE_URI = 'sqlite:///data.db'
DEFAULT_API_PREFIX = 'api/v1'
DEFAULT_PASSWORD_SIZE = 8
DEFAULT_EXPRIE_TOKEN = 30
DEFAULT_EXPIRE_ACCESS = 5

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
