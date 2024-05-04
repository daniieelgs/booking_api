
import os
import traceback
from dotenv import load_dotenv
from flask import request

from flask_jwt_extended import get_jwt_identity, jwt_required
from flask_smorest import Blueprint, abort
from flask.views import MethodView
from sqlalchemy.exc import SQLAlchemyError, IntegrityError

from db import commit, addAndCommit, deleteAndFlush, rollback

from globals import DEBUG, IMAGE_TYPE_GALLERY, IMAGE_TYPE_LOGOS, IMAGES_FOLDER, PARAM_FILE_NAME
from helpers.ImageController import checkRequestFile
from helpers.error.ImageError.InvalidExtensionException import InvalidExtensionException
from helpers.error.ImageError.InvalidFilenameException import InvalidFilenameException
from helpers.error.ImageError.NotFileException import NotFileException
from helpers.path import createPathFromLocal, generateImagePath, generatePagePath, removeFile, saveFile
from models.file import FileModel
from schema import FileSchema

#TODO: Cambiar a almacenamiento online

blp = Blueprint('files', __name__, description='Sistema de almacenamiento de archivos.')

def generateURLImage(local_id, image_type, name):
            
    load_dotenv()

    PUBLIC_FOLDER_URL = os.getenv('PUBLIC_FOLDER_URL', None)
    
    return {'url': f'/{PUBLIC_FOLDER_URL}/images/local/{local_id}/{image_type}/{name}'}

def generateURLPage(local_id, name):
            
    load_dotenv()

    PUBLIC_FOLDER_URL = os.getenv('PUBLIC_FOLDER_URL', None)
    
    return {'url': f'/{PUBLIC_FOLDER_URL}/pages/local/{local_id}/{name}'}

def saveRequestFile(request, path_generator_callback, generate_url_callback, update_if_conflict = False):

    try:
        file, filename = checkRequestFile(request)
        
        path = path_generator_callback(filename)
        
        try:
            saveFile(file, path, get_jwt_identity(), update_if_conflict)
        except FileNotFoundError:
            createPathFromLocal(get_jwt_identity())
            saveFile(file, path, get_jwt_identity(), update_if_conflict)      
            
        image = FileModel.query.filter_by(local_id = get_jwt_identity(), path = path).first()
        
        if not image:
            image = FileModel(local_id = get_jwt_identity(), name = filename, path = path, mimetype = file.mimetype)
        elif not update_if_conflict:
            raise IntegrityError()
            
        addAndCommit(image)
    except (InvalidExtensionException, InvalidFilenameException, NotFileException) as e:
        abort(400, message=str(e))
    except (IntegrityError, FileExistsError) as e:
        traceback.print_exc()
        abort(409, message='The file already exists')
    except SQLAlchemyError as e:
        traceback.print_exc()
        rollback()
        abort(500, message = str(e) if DEBUG else 'Cannot upload the file')
    
    return generate_url_callback(filename)
      
def saveImage(request, image_type):     
    return saveRequestFile(request, lambda filename: generateImagePath(filename, image_type), lambda filename: generateURLImage(get_jwt_identity(), image_type, filename))
        
def savePage(request):
    return saveRequestFile(request, generatePagePath, lambda filename: generateURLPage(get_jwt_identity(), filename), update_if_conflict = True)
    
def deleteFile(local_id, path):
    file = FileModel.query.filter_by(local_id = local_id, path = path).first_or_404()
    try:
        deleteAndFlush(file)
        removeFile(local_id, path)
        commit()
    except FileNotFoundError:
        rollback()
        abort(404, message='The file does not exist.')
    except SQLAlchemyError as e:
        traceback.print_exc()
        rollback()
        abort(500, message = str(e) if DEBUG else 'Cannot delete the fuke')
    
def deleteImage(name, image_type):
    return deleteFile(get_jwt_identity(), generateImagePath(name, image_type))
        
def deletePage(name):
    return deleteFile(get_jwt_identity(), generatePagePath(name))
        
@blp.route('local/<string:local_id>/logos')
class LogosImages(MethodView):
    
    def get(self, local_id):
        """
        Devuelve todas las imágenes de logos.
        """
        images = FileModel.query.filter_by(local_id = local_id).filter(FileModel.path.ilike(os.path.join(IMAGES_FOLDER, IMAGE_TYPE_LOGOS).replace("\\", "/") + '%')).all()
        return [generateURLImage(local_id, IMAGE_TYPE_LOGOS, image.name) for image in images]
    
@blp.route('logos')
class LogosImagesUpload(MethodView):

    @jwt_required(refresh=True)   
    @blp.response(409, description='La imagen ya existe.')
    @blp.response(400, description='La imagen no es válida, el nombre de la imagen no es válido o la extensión no es válida.')
    @blp.response(201, FileSchema) 
    def post(self):
        f"""
        Obtiene todas las imágenes de logos. Parameter name: {PARAM_FILE_NAME}
        """
        return saveImage(request, IMAGE_TYPE_LOGOS)

@blp.route('logos/<string:name>')
class LogosImagesUpload(MethodView):

    @jwt_required(refresh=True)   
    @blp.response(404, description='La imagen no existe.')
    @blp.response(204, description='La imagen ha sido eliminada.') 
    def delete(self, name):
        f"""
        Elimina una imagen de logo.
        """
        deleteImage(name, IMAGE_TYPE_LOGOS)
        
        return {}

@blp.route('/local/<string:local_id>/gallery')
class GalleryImages(MethodView):
    def get(self, local_id):
        f"""
        Devuelve todas las imágenes de la galería.
        """
        images = FileModel.query.filter_by(local_id = local_id).filter(FileModel.path.ilike(os.path.join(IMAGES_FOLDER, IMAGE_TYPE_GALLERY).replace("\\", "/") + '%')).all()
        return [generateURLImage(local_id, IMAGE_TYPE_GALLERY, image.name) for image in images]
    
@blp.route('gallery')
class GalleryImagesUpload(MethodView):

    @jwt_required(refresh=True)   
    @blp.response(409, description='La imagen ya existe.')
    @blp.response(400, description='El archivo no es válido, el nombre de la imagen no es válido o la extensión no es válida.')
    @blp.response(201, FileSchema) 
    def post(self):
        f"""
        Sube una nueva imagen de galería. Parameter name: {PARAM_FILE_NAME}
        """
        return saveImage(request, IMAGE_TYPE_GALLERY)
    
@blp.route('gallery/<string:name>')
class LogosImagesUpload(MethodView):

    @jwt_required(refresh=True)   
    @blp.response(404, description='La imagen no existe.')
    @blp.response(204, description='La imagen ha sido eliminada.') 
    def delete(self, name):
        f"""
        Elimina una imagen de la galería.
        """
        deleteImage(name, IMAGE_TYPE_LOGOS)
        
        return {}
    
@blp.route('pages')
class PagesUpload(MethodView):
    
    @jwt_required(refresh=True)   
    @blp.response(409, description='El archivo ya existe.')
    @blp.response(400, description='El archivo no es válido, el nombre del archivo no es válido o la extensión no es válida.')
    @blp.response(201, FileSchema) 
    @jwt_required(refresh=True)
    def post(self):
        f"""
        Sube una nueva página. Parameter name: {PARAM_FILE_NAME}
        """
        return savePage(request)

@blp.route('pages/<string:name>')
class PagesDelete(MethodView):
    
    @jwt_required(refresh=True)   
    @blp.response(404, description='La página no existe.')
    @blp.response(204, description='La página ha sido eliminada.') 
    def delete(self, name):
        f"""
        Elimina una página.
        """
        deletePage(name)
        
        return {}
    
