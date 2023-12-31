
import os
import traceback
from dotenv import load_dotenv
from flask import request

from flask_jwt_extended import get_jwt, get_jwt_identity, jwt_required
from flask_smorest import Blueprint, abort
from flask.views import MethodView
from sqlalchemy.exc import SQLAlchemyError, IntegrityError

from passlib.hash import pbkdf2_sha256

from db import deleteAndCommit, addAndCommit, rollback

from globals import DEBUG, IMAGE_TYPE_GALLERY, IMAGE_TYPE_LOGOS, PARAM_FILE_NAME
from helpers.ImageController import checkRequestFile
from helpers.error.ImageError.InvalidExtensionException import InvalidExtensionException
from helpers.error.ImageError.InvalidFilenameException import InvalidFilenameException
from helpers.error.ImageError.NotFileException import NotFileException
from helpers.path import savePath
from models.image import ImageModel
from schema import ImageSchema

blp = Blueprint('images', __name__, description='images CRUD')

def generateURL(local_id, image_type, filename):
            
    load_dotenv()

    PUBLIC_FOLDER_URL = os.getenv('PUBLIC_FOLDER_URL', None)
    
    
    return {'url': f'{PUBLIC_FOLDER_URL}/images/local/{local_id}/{image_type}/{filename}'}

def saveImage(request, image_type):
        
    try:
        file, filename = checkRequestFile(request)
        savePath(file, filename, image_type, get_jwt_identity())
        image = ImageModel(local_id = get_jwt_identity(), name = filename, filename = filename, type = image_type, mimetype = file.mimetype)
        addAndCommit(image)
    except (InvalidExtensionException, InvalidFilenameException, NotFileException) as e:
        abort(400, message=str(e))
    except IntegrityError as e:
        traceback.print_exc()
        abort(409, message='The image already exists')
    except SQLAlchemyError as e:
        traceback.print_exc()
        rollback()
        abort(500, message = str(e) if DEBUG else 'Cannot upload the image')
      
    return generateURL(get_jwt_identity(), image_type, filename)
        
@blp.route('local/<string:local_id>/logos')
class LogosImages(MethodView):
    
    @blp.response(201, ImageSchema(many=True)) 
    def get(self, local_id):
        """
        Returns the logos images
        """
        images = ImageModel.query.filter_by(local_id = local_id, type = IMAGE_TYPE_LOGOS).all()
        return [generateURL(local_id, image.type, image.filename) for image in images]
    
@blp.route('logos')
class LogosImagesUpload(MethodView):

    @jwt_required(refresh=True)   
    @blp.response(409, description='The image already exists')
    @blp.response(400, description='The file is not valid. The filename is not valid. The extension is not valid')
    @blp.response(201, ImageSchema) 
    def post(self):
        f"""
        Get all logos images. Parameter name: {PARAM_FILE_NAME}
        """
        return saveImage(request, IMAGE_TYPE_LOGOS)

@blp.route('/local/<string:local_id>/gallery')
class GalleryImages(MethodView):
    def get(self, local_id):
        f"""
        Get all gallery images.
        """
        images = ImageModel.query.filter_by(local_id = local_id, type = IMAGE_TYPE_GALLERY).all()
        return [generateURL(local_id, image.type, image.filename) for image in images]
    
@blp.route('gallery')
class GalleryImagesUpload(MethodView):

    @jwt_required(refresh=True)   
    @blp.response(409, description='The image already exists')
    @blp.response(400, description='The file is not valid. The filename is not valid. The extension is not valid')
    @blp.response(201, ImageSchema) 
    def post(self):
        f"""
        Uploads a new gallery image. Parameter name: {PARAM_FILE_NAME}
        """
        return saveImage(request, IMAGE_TYPE_GALLERY)
    
