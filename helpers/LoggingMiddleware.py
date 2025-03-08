import functools
import json
import traceback
from flask import Request, Response, request
import werkzeug

from globals import log
from helpers.security import generateUUID
from db import db

def default_json_encoder(obj):
    if isinstance(obj, db.Model):
        return obj.to_dict()
    return obj

def log_route(f):
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        uuid = generateUUID()
        log("Request received", uuid=uuid, request=request)
        
        try:
            response = f(*args, **kwargs, _uuid=uuid)
        except werkzeug.exceptions.HTTPException as e:
            #log response status and message
            response = Response(response=json.dumps({"message": e.description}), status=e.code, mimetype='application/json')
            log("Response generated", uuid=uuid, request=request, save_cache=True, response=response)
            raise e
        except Exception as e:
            traceback.print_exc()
            response = Response(response=json.dumps({"message": "Internal server error"}), status=500, mimetype='application/json')
            log("FATAL ERROR", uuid=uuid, request=request, error=e, level="ERROR", save_cache=True, response=response)
            raise e

        if not isinstance(response, Response):
            response = Response(response=json.dumps(response), mimetype='application/json')
           
            
        log("Response generated", uuid=uuid, request=request, response=response, save_cache=True)

        return response

    return decorated_function