from flask import request
from flask_smorest import Blueprint, abort
from flask.views import MethodView

from globals import DEBUG, log
from helpers.LoggingMiddleware import log_route
from helpers.ReportController import buildRequestMeta, getMaxReportSize, saveReport
from schema import FallbackReportResponseSchema

blp = Blueprint('report', __name__, description='Reportes de errores capturados por el frontend.')


@blp.route('/fallback')
class FallbackReport(MethodView):

    @log_route
    @blp.response(500, description='No se pudo almacenar el reporte.')
    @blp.response(413, description='El reporte es demasiado grande.')
    @blp.response(400, description='El cuerpo no es un JSON válido.')
    @blp.response(201, FallbackReportResponseSchema)
    def post(self, _uuid=None):
        """
        Registra un reporte de fallback del frontend (p.e. cuando el servidor principal
        no responde y se reintenta contra el secundario). No requiere autenticación y
        admite cualquier JSON.
        """
        max_report_size = getMaxReportSize()
        content_length = request.content_length

        if content_length is not None and content_length > max_report_size:
            log("Report rejected: the payload is too large.", uuid=_uuid, level='WARNING')
            abort(413, message='The report is too large.')

        raw_body = request.get_data(cache=True)

        if not raw_body:
            abort(400, message='The request body is empty.')

        if len(raw_body) > max_report_size:
            log("Report rejected: the payload is too large.", uuid=_uuid, level='WARNING')
            abort(413, message='The report is too large.')

        report = request.get_json(silent=True, force=True)

        if report is None:
            abort(400, message='The request body is not a valid JSON.')

        try:
            report_id, report_datetime = saveReport(report, buildRequestMeta(request))
        except Exception as e:
            log("Could not save the report.", uuid=_uuid, level='ERROR', error=e)
            abort(500, message=str(e) if DEBUG else 'Could not save the report.')

        log("Report saved.", uuid=_uuid)

        return {'id': report_id, 'datetime': report_datetime}
