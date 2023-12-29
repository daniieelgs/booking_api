from datetime import datetime, timedelta
from globals import DATE_GET, DATETIME_END_GET, DATETIME_INIT_GET, DAYS_GET, FORMAT_GET
from helpers.error.DataError.UnspecifedDateException import UnspecifedDateException

DEFAULT_FORMAT = '%Y-%m-%d %H:%M:%S'
DEFAULT_FORMAT_DATA = '%Y-%m-%d'

def getDataRequest(request, date_search = True, datetime_init_end_search = True, field_date = DATE_GET, field_datetime_init = DATETIME_INIT_GET, field_datetime_end = DATETIME_END_GET, field_format = FORMAT_GET):
    date = request.args.get(field_date, None)
    datetime_init = request.args.get(field_datetime_init, None)
    datetime_end = request.args.get(field_datetime_end, None)
    
    try:
        if date and date_search:
            format = request.args.get(field_format, DEFAULT_FORMAT_DATA)
            date = datetime.strptime(date, format)
            datetime_init = datetime.combine(date, datetime.min.time())
            datetime_end = datetime.combine(date, datetime.max.time())
        elif datetime_init and datetime_end and datetime_init_end_search:
            format = request.args.get(field_format, DEFAULT_FORMAT)
            datetime_init = datetime.strptime(datetime_init, format)
            datetime_end = datetime.strptime(datetime_end, format)
        else:
            raise UnspecifedDateException()
    except ValueError:
        raise ValueError('Invalid date format.')
        
    return datetime_init, datetime_end
    
def getWeekDataRequest(request, field_date = DATE_GET, field_format = FORMAT_GET, field_days = DAYS_GET):
    
    date = request.args.get(field_date, None)
    format = request.args.get(field_format, DEFAULT_FORMAT_DATA)
    days = request.args.get(field_days, 7)
    
    datetime_init = None
    datetime_end = None
    
    try:
        if date:
            date = datetime.strptime(date, format)
            week_day = date.weekday()
            date = date - timedelta(days=week_day)
            datetime_init = datetime.combine(date, datetime.min.time())
            datetime_end = datetime.combine(date, datetime.max.time()) + timedelta(days=days)
        else:
            raise UnspecifedDateException()
    except ValueError:
        raise ValueError('Invalid date format.')
    
    return datetime_init, datetime_end