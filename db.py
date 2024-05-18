import traceback
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy import create_engine

from datetime import datetime

db = SQLAlchemy()

def exists(model):
    if not model.id: return False
    
    instance = db.session.query(model.__class__).get(model.id)
    return instance is not None

def addDateTimes(model):
    
    try:    
        
        if model:
            
            model.datetime_updated = datetime.utcnow() #TODO check
            
            if not exists(model): model.datetime_created = model.datetime_updated
    except:
        traceback.print_exc()
    
    return model

def addAndCommit(*models, session = None, rollback = True):
    
    if len(models) == 0: return False
    
    try:
        for model in models:
            if model:db.session.add(addDateTimes(model))
            
        db.session.commit() if session is None else session.commit()
    except Exception as e:
        active_session = session if session is not None else db.session
        if rollback: active_session.rollback()
        raise e
    
    return True

def deleteAndCommit(*models, session = None, rollback = True):
    
    if len(models) == 0: return False
    try:
        for model in models:
            if model:
                db.session.refresh(model)
                db.session.delete(model)
        db.session.commit() if session is None else session.commit()
    except Exception as e:
        active_session = session if session is not None else db.session
        if rollback: active_session.rollback()
        raise e
        

    return True

def deleteAndFlush(*models, session = None, rollback = True):
    
    if len(models) == 0: return False
    
    try:
        for model in models:
            if model: db.session.delete(model) if session is None else session.delete(model)

        db.session.flush()
    except Exception as e:
        active_session = session if session is not None else db.session
        if rollback: active_session.rollback()
        raise e
    
    return True

def addAndFlush(*models, session = None, rollback = True):
    
    if len(models) == 0: return False
        
    try:
        for model in models:
            model = addDateTimes(model)
            if model: db.session.add(model) if session is None else session.add(model)

        db.session.flush()
    except Exception as e:
        active_session = session if session is not None else db.session
        if rollback: active_session.rollback()
        raise e

    return True

def new_session(engine):
    Session = sessionmaker(bind=engine)
    return Session()

def beginSession():
    return db.session.begin()

def rollback(session = None):
    db.session.rollback() if session is None else session.rollback()
    
def commit(session = None):
    db.session.commit() if session is None else session.commit()
    
def flush(session = None):
    db.session.flush() if session is None else session.flush()