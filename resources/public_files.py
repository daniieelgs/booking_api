
from flask import make_response

from flask_smorest import Blueprint, abort
from flask.views import MethodView

from globals import IMAGE_TYPE_GALLERY, IMAGE_TYPE_LOGOS
from helpers.path import generateImagePath, generatePagePath, getFile
from models.file import FileModel


blp = Blueprint('public_files', __name__, description='Obtiene archivos públicos.')

def generateFileResponse(local_id, path):
    image = FileModel.query.filter_by(local_id = local_id, path = path).first_or_404()
    try:
        r = getFile(local_id, image.path)
    except FileNotFoundError:
        abort(404, message='The file does not exist.')

    response = make_response(r)
    response.headers['Content-Type'] = image.mimetype
    response.headers['Content-Disposition'] = f'inline; filename="{image.name}"'
    
    return response
       
@blp.route('/images/local/<string:local_id>/logos/<string:name>')
class LogoImage(MethodView):

    @blp.response(404, description='La imagen no existe.')
    def get(self, local_id, name):
        """
        Devuelve el logo del local.
        """
        
        return generateFileResponse(local_id, generateImagePath(name, IMAGE_TYPE_LOGOS))
            
@blp.route('/images/local/<string:local_id>/gallery/<string:name>')
class GalleryImage(MethodView):

    @blp.response(404, description='La imagen no existe.')
    def get(self, local_id, name):
        """
        Devuelve una imagen de la galería.
        """
        return generateFileResponse(local_id, generateImagePath(name, IMAGE_TYPE_GALLERY))

@blp.route('/pages/local/<string:local_id>/<string:page>')
class Page(MethodView):
    
    def get(self, local_id, page):
        """
        Devuelve una página.
        """
        return generateFileResponse(local_id, generatePagePath(page))