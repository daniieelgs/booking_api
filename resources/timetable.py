from flask.views import MethodView
from flask_smorest import Blueprint, abort
from helpers.BookingController import checkTimetableBookings
from helpers.TimetableController import getTimetable, validateTimetable
from helpers.error.BookingError.BookingsConflictException import BookingsConflictException
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

blp = Blueprint('timetable', __name__, description='Timetable CRUD')

@blp.route('/local/<string:local_id>/week')
class TimetableWeek(MethodView):

    @blp.response(404, description='The local was not found')
    @blp.response(200, TimetableSchema(many=True))
    def get(self, local_id):
        """
        Retrieves timetable from the week.
        """      
        return getTimetable(LocalModel.query.get_or_404(local_id).id)

@blp.route('/local/<string:local_id>/week/<string:week>')
class TimetableDay(MethodView):
    
    @blp.response(404, description='The local was not found. The day was not found.')
    @blp.response(204, description='The day does not have timetable.')
    @blp.response(200, TimetableSchema(many=True))
    def get(self, local_id, week):
        """
        Retrieves timetable from a day.
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
        Retrieves all weekdays.
        """
        return WeekdayModel.query.all()
@blp.route('/week/<string:week>')
class TimetableDayDelete(MethodView):
    @blp.response(404, description='The local was not found. The day was not found.')
    @blp.response(204, description='The timetable day was deleted.')
    @jwt_required(refresh=True)
    def delete(self, week):
        """
        Deletes a timetable day.
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
    @blp.response(404, description='The local was not found. The day was not found.')
    @blp.response(409, description='The timetable is overlapping. The opening time is greater than the closing time. There is a booking that overlaps with the timetable.')
    @blp.response(200, TimetableSchema(many=True))
    @jwt_required(refresh=True)
    def put(self, timetables_data):
        """
        Updates the timetable from a local.
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
        except BookingsConflictException as e:
            rollback()
            abort(409, message = str(e))
        except SQLAlchemyError as e:
            traceback.print_exc()
            rollback()
            abort(500, message = str(e) if DEBUG else 'Could not create the timetable.')
        
        return timetables