
from db import deleteAndCommit, rollback
from globals import DEFAULT_LOCATION_TIME
from helpers.DatetimeHelper import isAware, naiveToAware, now as nowIn
from helpers.error.ClosedDaysError.BadDatetimesClosedDaysException import BadDatetimesClosedDaysException
from helpers.error.ClosedDaysError.ConflictClosedDaysException import ConflictClosedDaysException
from models.closed import ClosedModel
from models.local import LocalModel
import datetime

def getLocalLocation(localId):
    local = LocalModel.query.get(localId)
    return local.location if local and local.location else DEFAULT_LOCATION_TIME

def getClosedDays(localId, datetime_init = None, datetime_end = None):
    closedDays = ClosedModel.query.filter_by(local_id=localId).all()
    
    location = getLocalLocation(localId)
    
    # closed days are naive wall-clock times of the local (see helpers/DatetimeHelper.py)
    now = nowIn(location).replace(tzinfo=None)
    deleted = []
    
    for closedDay in [c for c in closedDays if c.datetime_end < now]:
        try:
            deleteAndCommit(closedDay)
            deleted.append(closedDay)
        except Exception:
            rollback()
    
    closedDays = [c for c in closedDays if c not in deleted]
    
    if datetime_init:
        if not isAware(datetime_init):
            datetime_init = naiveToAware(datetime_init, location)
        closedDays = [closedDay for closedDay in closedDays if naiveToAware(closedDay.datetime_end, location) >= datetime_init]
        
    if datetime_end:
        if not isAware(datetime_end):
            datetime_end = naiveToAware(datetime_end, location)
        closedDays = [closedDay for closedDay in closedDays if naiveToAware(closedDay.datetime_init, location) <= datetime_end]
        
    return closedDays

def checkClosedDay(localId, datetime_init, datetime_end, closedDayId = None):
    
    if datetime_init >= datetime_end:
        raise BadDatetimesClosedDaysException('La fecha de inicio debe ser menor a la fecha de fin.')
        
    closedDays = getClosedDays(localId)
    
    for closedDay in closedDays:
        if closedDayId and closedDay.id == closedDayId:
            continue
        if closedDay.datetime_init < datetime_end and datetime_init < closedDay.datetime_end:
            raise ConflictClosedDaysException('La fecha de cierre se cruza con otra fecha de cierre.')
            
    return True