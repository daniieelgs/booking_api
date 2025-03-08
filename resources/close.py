import traceback
from db import addAndCommit, deleteAndCommit, rollback
from flask.views import MethodView
from flask_smorest import Blueprint, abort
from flask_jwt_extended import jwt_required, get_jwt_identity
from globals import DEBUG
from helpers.closed import checkClosedDay, getClosedDays
from helpers.error.ClosedDaysError.BadDatetimesClosedDaysException import BadDatetimesClosedDaysException
from helpers.error.ClosedDaysError.ConflictClosedDaysException import ConflictClosedDaysException
from models.closed import ClosedModel
from models.local import LocalModel
from schema import CloseDaysParams, CloseDaysSchema

blp = Blueprint('close', __name__, description='CRUD de dias de cierres.')

@blp.route('')
class CloseDays(MethodView):
    
    @blp.arguments(CloseDaysSchema)
    @blp.response(400, description='La fecha de inicio debe ser menor a la fecha de fin.')
    @blp.response(409, description='La fecha de cierre se cruza con otra fecha de cierre.')
    @blp.response(200, CloseDaysSchema)
    @jwt_required(refresh=True)
    def post(self, data):
        """
        Agrega una fecha de cierre
        """
        
        local = LocalModel.query.get(get_jwt_identity())
        
        datetime_init = data['datetime_init']
        datetime_end = data['datetime_end']
                
        try:           
            
            checkClosedDay(local.id, datetime_init, datetime_end)
            
            closed = ClosedModel(local_id=local.id, datetime_init=datetime_init, datetime_end=datetime_end, description=data.get('description'))
            addAndCommit(closed)            
            return closed
            
        except BadDatetimesClosedDaysException as e:
            abort(400, message = str(e))
        except ConflictClosedDaysException as e:
            abort(409, message = str(e))
        except Exception as e:
            traceback.print_exc()
            rollback()
            abort(500, message = str(e) if DEBUG else 'Could save the closed day.')
            
    @blp.arguments(CloseDaysParams, location='query')
    @blp.response(200, CloseDaysSchema(many=True))
    @jwt_required(refresh=True)
    def get(self, params):
        """
        Devuelve las fechas de cierre
        """
        
        local = LocalModel.query.get(get_jwt_identity())
        
        return getClosedDays(local.id, params.get('datetime_init'), params.get('datetime_end'))
    
@blp.route('/<string:close_id>')
class CloseDay(MethodView):
    
    @blp.response(404, description='La fecha de cierre no existe.')
    @blp.response(204, description='La fecha de cierre ha sido eliminada.')
    @jwt_required(refresh=True)
    def delete(self, close_id):
        """
        Elimina una fecha de cierre
        """
        
        closedDay = ClosedModel.query.get_or_404(close_id)
        
        try:
            deleteAndCommit(closedDay)
            return {}
        except Exception as e:
            traceback.print_exc()
            rollback()
            abort(500, message = str(e) if DEBUG else 'Could not delete the closed day.')
    
    @blp.arguments(CloseDaysSchema)
    @blp.response(400, description='La fecha de inicio debe ser menor a la fecha de fin.')
    @blp.response(409, description='La fecha de cierre se cruza con otra fecha de cierre.')
    @blp.response(404, description='La fecha de cierre no existe.')
    @blp.response(200, CloseDaysSchema)
    @jwt_required(refresh=True)
    def put(self, data, close_id):
        """
        Modifica una fecha de cierre
        """
        
        closedDay = ClosedModel.query.get_or_404(close_id)
        
        try:
            checkClosedDay(closedDay.local_id, data['datetime_init'], data['datetime_end'], closedDay.id)
            
            closedDay.datetime_init = data['datetime_init']
            closedDay.datetime_end = data['datetime_end']
            closedDay.description = data.get('description')
            
            addAndCommit(closedDay)
        
            return closedDay
        
        except BadDatetimesClosedDaysException as e:
            abort(400, message = str(e))
        except ConflictClosedDaysException as e:
            abort(409, message = str(e))
        except Exception as e:
            traceback.print_exc()
            rollback()
            abort(500, message = str(e) if DEBUG else 'Could save the closed day.')
            
@blp.route('/local/<string:local_id>')
class CloseDaysLocal(MethodView):
    
    @blp.arguments(CloseDaysParams, location='query')
    @blp.response(404, description='El local no existe.')
    @blp.response(200, CloseDaysSchema(many=True))
    def get(self, params, local_id):
        """
        Devuelve las fechas de cierre de un local
        """
        
        local = LocalModel.query.get_or_404(local_id)
        
        return getClosedDays(local.id, params.get('datetime_init'), params.get('datetime_end'))