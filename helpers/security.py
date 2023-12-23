import secrets
import string
import datetime
import traceback
import uuid

from globals import PASSWORD_SIZE, EXPIRE_TOKEN, EXPIRE_ACCESS

from sqlalchemy.exc import SQLAlchemyError
from flask_jwt_extended import create_access_token, create_refresh_token, decode_token

from db import db, addAndCommit
from models.session_token import SessionTokenModel

def generatePassword(size = PASSWORD_SIZE):
    characters = string.ascii_letters + string.digits + string.punctuation
    return ''.join(secrets.choice(characters) for i in range(size))

def generateTokens(localId, access_token = False, refresh_token = True, claims = {}, expire_refresh = datetime.timedelta(days=EXPIRE_TOKEN), expire_access = datetime.timedelta(minutes=EXPIRE_ACCESS)):
    
    token_fresh = None
    token_refresh = None
    
    saveToken = []
       
    if access_token:
        tokenId = uuid.uuid4().hex
        claims['token'] = tokenId
        token_fresh = create_access_token(identity=localId, additional_claims=claims, expires_delta=expire_access, fresh=True)
        
        saveToken.append(token_fresh)
        
    if refresh_token:
        tokenId = uuid.uuid4().hex
        claims['token'] = tokenId
        token_refresh = create_refresh_token(identity=localId, additional_claims=claims, expires_delta=expire_refresh)
        
        saveToken.append(token_refresh)
       
    addAndCommit(*[SessionTokenModel(id = decode_token(token)['token'], jti = decode_token(token)['jti'], local_id = localId) for token in saveToken])
    
    if token_fresh and token_refresh: 
        return token_fresh, token_refresh

    return token_fresh if token_fresh else token_refresh
 
def generateUUID():
    return uuid.uuid4().hex