from db import db
from sqlalchemy import UniqueConstraint

class WorkGroupModel(db.Model):
    __tablename__ = 'work_group'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(45), nullable=False)
    description = db.Column(db.Text, nullable=True)
    local_id = db.Column(db.String(32), db.ForeignKey('local.id')) 
    datetime_created = db.Column(db.DateTime, nullable=True)
    datetime_updated = db.Column(db.DateTime, nullable=True)

    workers = db.relationship('WorkerModel', secondary='work_group_worker', lazy='dynamic')
    services = db.relationship('ServiceModel', back_populates='work_group', lazy='dynamic')
    local = db.relationship('LocalModel', back_populates='work_groups')

    __table_args__ = (UniqueConstraint('name', 'local_id', name='name'),)
