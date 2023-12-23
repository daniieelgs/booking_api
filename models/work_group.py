from db import db

class WorkGroupModel(db.Model):
    __tablename__ = 'work_group'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(45), nullable=False)
    description = db.Column(db.Text)
    local_id = db.Column(db.String(32), db.ForeignKey('local.id')) 
    datetime_created = db.Column(db.DateTime, nullable=True)
    datetime_updated = db.Column(db.DateTime, nullable=True)

    # Relación con WorkerModel
    workers = db.relationship('WorkerModel', secondary='work_group_worker', backref=db.backref('work_groups', lazy='dynamic'))
    services = db.relationship('ServiceModel', back_populates='work_group', lazy='dynamic')
    local = db.relationship('LocalModel', back_populates='work_groups')

