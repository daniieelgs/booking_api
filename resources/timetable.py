from flask.views import MethodView
from flask_smorest import Blueprint, abort
from helpers.BookingController import checkTimetableBookings
from helpers.TimetableController import getTimetable, validateTimetable
from helpers.error.BookingError.BookingsConflictException import BookingsConflictException
from helpers.error.LocalError.LocalNotFoundException import LocalNotFoundException
from helpers.error.TimetableError.TimetableOverlapsException import TimetableOverlapsException
from helpers.error.TimetableError.TimetableTimesException import TimetableTimesException
from models.local import LocalModel
from db import db, addAndFlush, addAndCommit, commit, deleteAndFlush, deleteAndCommit, flush, rollback
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy.exc import SQLAlchemyError, OperationalError
import traceback

from globals import DEBUG
from models.timetable import TimetableModel
from models.weekday import WeekdayModel
from schema import TimetableSchema, WeekDaySchema

blp = Blueprint('timetable', __name__, description='CRUD de horarios.')

@blp.route('/local/<string:local_id>/week')
class TimetableWeek(MethodView):

    @blp.response(404, description='El local no existe.')
    @blp.response(200, TimetableSchema(many=True))
    def get(self, local_id):
        """
        Devuelve el horario de la semana del local.
        """      
        return getTimetable(LocalModel.query.get_or_404(local_id).id)

@blp.route('/local/<string:local_id>/week/<string:week>')
class TimetableDay(MethodView):
    
    @blp.response(404, description='El local no existe o el día no existe.')
    @blp.response(204, description='No hay horario para el día indicado.')
    @blp.response(200, TimetableSchema(many=True))
    def get(self, local_id, week):
        """
        Devuelve el horario de un día de la semana del local.
        """      
        LocalModel.query.get_or_404(local_id)
        
        week = week.upper()
        
        weekday_id = WeekdayModel.query.filter_by(weekday=week).first()
        
        if not weekday_id: abort(404, message=f'The day [{week}] was not found.')
        
        weekday_id = weekday_id.id
        
        weekdays = getTimetable(local_id, weekday_id)
        
        return weekdays if weekdays else ({}, 204)
    
@blp.route('/weekdays')
class TimetableDayDelete(MethodView):
    
    @blp.response(200, WeekDaySchema(many=True))
    def get(self):
        """
        Devuelve los identificadores de los días de la semana.
        """
        return WeekdayModel.query.all()
@blp.route('/week/<string:week>')
class TimetableDayDelete(MethodView):
    @blp.response(404, description='El local no existe o el día no existe.')
    @blp.response(204, description='El horario ha sido eliminado.')
    @jwt_required(refresh=True)
    def delete(self, week):
        """
        Elimina el horario de un día de la semana del local.
        """
        local = LocalModel.query.get(get_jwt_identity())
        
        week = week.upper()
        
        weekday_id = WeekdayModel.query.filter_by(weekday=week).first()
        
        if not weekday_id: abort(404, message=f'The day [{week}] was not found.')
        
        weekday_id = weekday_id.id
        
        timetable = local.timetables.filter_by(weekday_id=weekday_id).all()
        
        try:
            deleteAndCommit(*timetable)
        except SQLAlchemyError as e:
            traceback.print_exc()
            rollback()
            abort(500, message = str(e) if DEBUG else 'Could not delete the timetable.')
            
@blp.route('')
class Timetable(MethodView):
    
    @blp.arguments(TimetableSchema(many=True))
    @blp.response(404, description='El local no existe o el día no existe.')
    @blp.response(409, description='El horario se superpone, la hora de apertura es mayor que la de cierre o hay una reserva que se superpone con el horario.')
    @blp.response(200, TimetableSchema(many=True))
    @jwt_required(refresh=True)
    def put(self, timetables_data):
        """
        Actualiza el horario del local.
        """
        local = LocalModel.query.get(get_jwt_identity())
        
        timetables = []
        
        for timetable_data in timetables_data:
            weekday_short = timetable_data.pop('weekday_short').upper()
            
            weekday = WeekdayModel.query.filter_by(weekday=weekday_short).first()
                    
            if not weekday: abort(404, message=f'The day [{weekday_short}] was not found.')
                    
            timetable = TimetableModel(**timetable_data)
            timetable.weekday = weekday
            timetable.local = local
            
            timetables.append(timetable)
        
        old_timetables = local.timetables.all()
                
        try: 
            deleteAndFlush(*old_timetables)
            flush()
            addAndFlush(*timetables)
            print("CHECKING TIMETABLES")
            validateTimetable(local.id)
            checkTimetableBookings(local.id)
            commit()
        except (TimetableOverlapsException, TimetableTimesException) as e:
            rollback()
            abort(409, message = str(e))
        except LocalNotFoundException as e:
            rollback()
            abort(404, message = str(e))
        except BookingsConflictException as e:
            rollback()
            abort(409, message = str(e))
        except SQLAlchemyError as e:
            traceback.print_exc()
            rollback()
            abort(500, message = str(e) if DEBUG else 'Could not create the timetable.')
        
        return timetables