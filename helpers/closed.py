
from db import deleteAndCommit, rollback
from helpers.DatetimeHelper import isAware, naiveToAware
from helpers.error.ClosedDaysError.BadDatetimesClosedDaysException import BadDatetimesClosedDaysException
from helpers.error.ClosedDaysError.ConflictClosedDaysException import ConflictClosedDaysException
from models.closed import ClosedModel
import datetime

def getClosedDays(localId, datetime_init = None, datetime_end = None):
    closedDays = ClosedModel.query.filter_by(local_id=localId).all()
        
    for closedDay in closedDays:
        if closedDay.datetime_end < datetime.datetime.now():
            try:
                deleteAndCommit(closedDay)
                closedDays.remove(closedDay)
            except:
                rollback()
    
    if datetime_init:
        if not isAware(datetime_init):
            datetime_init = naiveToAware(datetime_init)
        closedDays = [closedDay for closedDay in closedDays if naiveToAware(closedDay.datetime_end )>= datetime_init]
        
    if datetime_end:
        if not isAware(datetime_end):
            datetime_end = naiveToAware(datetime_end)
        closedDays = [closedDay for closedDay in closedDays if naiveToAware(closedDay.datetime_init) <= datetime_end]
        
    return closedDays

def checkClosedDay(localId, datetime_init, datetime_end, closedDayId = None):
    
    if datetime_init >= datetime_end:
        raise BadDatetimesClosedDaysException('La fecha de inicio debe ser menor a la fecha de fin.')
        
    closedDays = getClosedDays(localId)
    
    for closedDay in closedDays:
        if closedDayId and closedDay.id == closedDayId:
            continue
        if closedDay.datetime_init <= datetime_init < closedDay.datetime_end or closedDay.datetime_init < datetime_end <= closedDay.datetime_end:
            raise ConflictClosedDaysException('La fecha de cierre se cruza con otra fecha de cierre.')
            
    return True