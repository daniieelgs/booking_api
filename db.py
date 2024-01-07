import traceback
from flask_sqlalchemy import SQLAlchemy

from datetime import datetime

db = SQLAlchemy()

def exists(model):
    if not model.id: return False

    instance = db.session.query(model.__class__).get(model.id)
    return instance is not None

def addDateTimes(model):
    
    try:    
        model.datetime_updated = datetime.utcnow()
        
        if not exists(model): model.datetime_created = model.datetime_updated
    except:
        traceback.print_exc()
    
    return model

def addAndCommit(*models):
    
    if len(models) == 0: return False
    
    try:
        for model in models:
            if model:db.session.add(addDateTimes(model))
            
        db.session.commit()
    except Exception as e:
        rollback()
        raise e
    
    return True

def deleteAndCommit(*models):
    
    if len(models) == 0: return False
    try:
        for model in models:
            db.session.refresh(model)
            if model: db.session.delete(model)
        db.session.commit()
    except Exception as e:
        rollback()
        raise e
        

    return True

def deleteAndFlush(*models, session = None):
    
    if len(models) == 0: return False
    
    try:
        for model in models:
            if model: db.session.delete(model) if session is None else session.delete(model)

        db.session.flush()
    except Exception as e:
        rollback()
        raise e
    
    return True

def addAndFlush(*models, session = None):
    
    if len(models) == 0: return False
    
    try:
        for model in models:
            model = addDateTimes(model)
            if model:db.session.add(model) if session is None else session.add(model)

        db.session.flush()
    except Exception as e:
        rollback()
        raise e

    return True

def rollback(session = None):
    db.session.rollback() if session is None else session.rollback()
    
def commit(session = None):
    db.session.commit() if session is None else session.commit()
    
def flush():
    db.session.flush()