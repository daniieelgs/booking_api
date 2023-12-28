
from models.timetable import TimetableModel


def getTimetable(local_id, weekday_id = None, datetime_init = None, datetime_end = None):
    if weekday_id:
        timetable =  TimetableModel.query.filter_by(local_id = local_id, weekday_id = weekday_id).order_by(TimetableModel.opening_time).all()
    else:
        timetable = TimetableModel.query.filter_by(local_id = local_id).order_by(TimetableModel.weekday_id, TimetableModel.opening_time).all()
        
    if datetime_init and datetime_end:
        timetable = [t for t in timetable if t.opening_time <= datetime_init.time() and t.closing_time >= datetime_end.time()]
        
    return timetable