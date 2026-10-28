from flask_smorest import Blueprint
from flask.views import MethodView

from globals import VERSION
from helpers.Database import ping_redis
from schema import HealthSchema, VersionSchema

blp = Blueprint('status', __name__, description='Estado y versión de la API.')


@blp.route('/health')
class Health(MethodView):

    @blp.response(200, HealthSchema)
    def get(self):
        """
        Comprueba que la API está funcionando. No requiere autenticación.
        Incluye el estado de Redis.
        """
        redis_ok = ping_redis()
        return {
            'status': 'ok' if redis_ok else 'degraded',
            'redis': 'ok' if redis_ok else 'error',
        }


@blp.route('/version')
class Version(MethodView):

    @blp.response(200, VersionSchema)
    def get(self):
        """
        Devuelve la versión de la API. No requiere autenticación.
        """
        return {'version': VERSION}
