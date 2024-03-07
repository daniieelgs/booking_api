from flask_jwt_extended import get_jwt_identity, jwt_required
from flask_smorest import Blueprint
from flask.views import MethodView
from globals import EMAIL_CONFIRMATION_PAGE, KEYWORDS_PAGES
from helpers.path import generatePagePath

from resources.public_files import generateFileResponse


blp = Blueprint('test', __name__)

@blp.route('<string:local_id>')
class Test(MethodView):
    
    # @jwt_required(refresh=True)
    def get(self, local_id):
        response = generateFileResponse(local_id, generatePagePath(EMAIL_CONFIRMATION_PAGE))
        
        body = response.get_data().decode('utf-8')
        
        
        body = body.replace(KEYWORDS_PAGES['CONFIRMATION_LINK'], 'https://www.google.com')
        
        return body