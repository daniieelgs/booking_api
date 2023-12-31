
import traceback
from flask import make_response

from flask_jwt_extended import get_jwt, get_jwt_identity, jwt_required
from flask_smorest import Blueprint, abort
from flask.views import MethodView
from sqlalchemy.exc import SQLAlchemyError, IntegrityError

from passlib.hash import pbkdf2_sha256

from db import deleteAndCommit, addAndCommit, rollback

from globals import DEBUG, IMAGE_TYPE_GALLERY, IMAGE_TYPE_LOGOS, LOCAL_ROLE
from helpers.path import getImage
from models.image import ImageModel


blp = Blueprint('public_images', __name__, description='get public images')

def generateImageResponse(local_id, name, type):
    image = ImageModel.query.filter_by(local_id = local_id, name = name, type = type).first_or_404()
    
    r = getImage(local_id, image.filename, image.type)

    response = make_response(r)
    response.headers['Content-Type'] = image.mimetype
    response.headers['Content-Disposition'] = f'inline; filename="{image.filename}"'
    
    return response
   
@blp.route('/local/<string:local_id>/logos/<string:name>')
class LogoImage(MethodView):
    def get(self, local_id, name):
        """
        Returns the logo image
        """
        
        return generateImageResponse(local_id, name, IMAGE_TYPE_LOGOS)
            
@blp.route('/local/<string:local_id>/gallery/<string:name>')
class GalleryImage(MethodView):
    def get(self, local_id, name):
        """
        Returns the gallery image
        """
        return generateImageResponse(local_id, name, IMAGE_TYPE_GALLERY)