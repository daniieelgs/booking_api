from flask_smorest import Blueprint
from flask.views import MethodView
from flask_smorest import abort

def generate_unavaliable_api(num_resources):
    
    blp = Blueprint(f'ua{num_resources}', __name__)
    
    path = ''
    
    for i in range(num_resources):
        path += f'/<string:resource{i}>'
    
    def unavailable_api():
        abort(503, message = 'API not available in performance test mode.')
    
    @blp.route(path)
    class UnavailableAPI(MethodView):
        def get(self, **args):
            unavailable_api()
            
        def post(self, **args):
            unavailable_api()
            
        def put(self, **args):
            unavailable_api()
            
        def patch(self, **args):
            unavailable_api()
            
        def delete(self, **args):
            unavailable_api()
                
    return blp
    