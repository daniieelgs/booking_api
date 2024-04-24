import os
import secrets
import string
import datetime
import traceback
import uuid

import jwt

from cryptography.fernet import Fernet


from globals import CRYPTO_KEY, DEFAULT_CRYPTO_JWT, JWT_ALGORITHM, LOCAL_ROLE, PASSWORD_SIZE, EXPIRE_TOKEN, EXPIRE_ACCESS, SECRET_JWT

from sqlalchemy.exc import SQLAlchemyError
from flask_jwt_extended import create_access_token, create_refresh_token, decode_token

from db import db, addAndCommit
from helpers.DatetimeHelper import now
from models.session_token import SessionTokenModel
from models.user_session import UserSessionModel

def generatePassword(size = PASSWORD_SIZE):
    characters = string.ascii_letters + string.digits + string.punctuation
    return ''.join(secrets.choice(characters) for i in range(size))

def generateTokens(identity, localId, access_token = False, refresh_token = True, claims = {}, expire_refresh = datetime.timedelta(days=EXPIRE_TOKEN), expire_access = datetime.timedelta(minutes=EXPIRE_ACCESS), user_role = LOCAL_ROLE):
    
    token_fresh = None
    token_refresh = None
    
    saveToken = []
       
    if access_token:
        tokenId = uuid.uuid4().hex
        claims['token'] = tokenId
        token_fresh = create_access_token(identity=identity, additional_claims=claims, expires_delta=expire_access, fresh=True)
        
        saveToken.append(token_fresh)
        
    if refresh_token:
        tokenId = uuid.uuid4().hex
        claims['token'] = tokenId
        token_refresh = create_refresh_token(identity=identity, additional_claims=claims, expires_delta=expire_refresh)
        
        saveToken.append(token_refresh)
       
    user_session_id = UserSessionModel.query.filter_by(user = user_role).first().id
       
    addAndCommit(*[SessionTokenModel(id = decode_token(token)['token'], jti = decode_token(token)['jti'], local_id = localId, user_session_id = user_session_id) for token in saveToken])
    
    if token_fresh and token_refresh: 
        return token_fresh, token_refresh

    return token_fresh if token_fresh else token_refresh
 
def getTokenId(token):
    return decode_token(token)['token']
 
def decodeToken(token):
    return decode_token(token)

def decodeJWT(token):
    return jwt.decode(token, key=SECRET_JWT, algorithms=[JWT_ALGORITHM])

def generateUUID():
    return uuid.uuid4().hex

def logOutAll(local_id):
    
    SessionTokenModel.query.filter(SessionTokenModel.local_id == local_id).delete()
    db.session.commit()
    
def encrypt_str(txt, key = CRYPTO_KEY):
    cipher_suite = Fernet(key)
    return cipher_suite.encrypt(txt.encode())

def decrypt_str(txt, key = CRYPTO_KEY):
    cipher_suite = Fernet(key)
    return cipher_suite.decrypt(txt).decode()