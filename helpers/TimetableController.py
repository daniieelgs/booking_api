
from sqlalchemy import and_, or_
from helpers.error.TimetableError.TimetableOverlapsException import TimetableOverlapsException
from helpers.error.TimetableError.TimetableTimesException import TimetableTimesException
from models.timetable import TimetableModel

def getTimetable(local_id, weekday_id = None, datetime_init = None, datetime_end = None):
    
    if weekday_id:
        timetable =  TimetableModel.query.filter_by(local_id = local_id, weekday_id = weekday_id).order_by(TimetableModel.opening_time).all() 
    else:
        timetable = TimetableModel.query.filter_by(local_id = local_id).order_by(TimetableModel.weekday_id, TimetableModel.opening_time).all()
        
    if datetime_init and datetime_end:
        timetable = [t for t in timetable if t.opening_time <= datetime_init.time() and t.closing_time >= datetime_end.time()]
        
    return timetable

def validateTimetable(local_id):
    

    timetables = getTimetable(local_id)
    
    for timetable in timetables:
        timetable:TimetableModel = timetable
        if timetable.opening_time >= timetable.closing_time:
            raise TimetableTimesException()
        
        query = TimetableModel.query.filter(
            TimetableModel.local_id == local_id,
            TimetableModel.weekday_id == timetable.weekday_id,
            TimetableModel.id != timetable.id,
            and_(
                TimetableModel.opening_time <= timetable.opening_time, TimetableModel.closing_time >= timetable.opening_time,
                or_(TimetableModel.opening_time <= timetable.closing_time, TimetableModel.closing_time >= timetable.closing_time),
                or_(timetable.opening_time <= TimetableModel.opening_time, timetable.closing_time >= TimetableModel.closing_time)
            )
        )
        
        if query.first():
            raise TimetableOverlapsException()
        
    return True
    