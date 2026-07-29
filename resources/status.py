from flask_smorest import Blueprint
from flask.views import MethodView

from globals import VERSION
from schema import HealthSchema, VersionSchema

blp = Blueprint('status', __name__, description='Estado y versión de la API.')


@blp.route('/health')
class Health(MethodView):

    @blp.response(200, HealthSchema)
    def get(self):
        """
        Comprueba que la API está funcionando. No requiere autenticación.
        """
        return {'status': 'ok'}


@blp.route('/version')
class Version(MethodView):

    @blp.response(200, VersionSchema)
    def get(self):
        """
        Devuelve la versión de la API. No requiere autenticación.
        """
        return {'version': VERSION}
