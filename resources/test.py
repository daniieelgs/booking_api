from flask_jwt_extended import get_jwt_identity, jwt_required
from flask_smorest import Blueprint
from flask.views import MethodView
from globals import EMAIL_CONFIRMATION_PAGE, KEYWORDS_PAGES
from helpers.path import generatePagePath

from resources.public_files import generateFileResponse

from celery.result import AsyncResult
from celery_app.tasks import check_booking


blp = Blueprint('test', __name__)

@blp.route('<string:local_id>')
class Test(MethodView):
    
    # @jwt_required(refresh=True)
    def get(self, local_id):
        response = generateFileResponse(local_id, generatePagePath(EMAIL_CONFIRMATION_PAGE))
        
        body = response.get_data().decode('utf-8')
        
        
        body = body.replace(KEYWORDS_PAGES['CONFIRMATION_LINK'], 'https://www.google.com')
        
        return body
    
@blp.route('celery')
class CeleryTest(MethodView):
    def get(self):
        
        response = check_booking.delay(1)
        
        return {"message": f"Task {response.id} started!"}
    
@blp.route('celery/<string:task_id>')
class CeleryTest(MethodView):
    def get(self, task_id):
        
        response = AsyncResult(task_id)
        
        return {
            "ready": response.ready(),
            "successful": response.successful(),
            "value": response.result if response.ready() else None,
        }   
    
@blp.route('celery/wait')
class CeleryTest(MethodView):
    def get(self):
        
        response = check_booking.wait(1)
        
        return {"response": response}