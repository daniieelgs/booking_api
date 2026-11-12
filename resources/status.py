from flask_smorest import Blueprint
from flask.views import MethodView

from globals import VERSION
from helpers.HealthController import get_health_status
from schema import HealthSchema, VersionSchema

blp = Blueprint('status', __name__, description='Estado y versión de la API.')


@blp.route('/health')
class Health(MethodView):

    @blp.response(200, HealthSchema)
    def get(self):
        """
        Estado global de la API. No requiere autenticación. Responde siempre 200; el valor de `status` indica el estado:
        `ok` (base de datos, Redis y worker de Celery funcionan), `degraded` (el worker no responde: las reservas
        funcionan pero los emails se retrasan), `error` (Redis no responde: no se pueden crear reservas) y
        `critical` (la base de datos no responde).
        """
        return {'status': get_health_status()}


@blp.route('/version')
class Version(MethodView):

    @blp.response(200, VersionSchema)
    def get(self):
        """
        Devuelve la versión de la API. No requiere autenticación.
        """
        return {'version': VERSION}
