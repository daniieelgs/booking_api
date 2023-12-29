from db import db

class WorkGroupWorkerModel(db.Model):
    __tablename__ = 'work_group_worker'
    
    id = db.Column(db.Integer, primary_key=True)
    work_group_id = db.Column(db.Integer, db.ForeignKey('work_group.id'), nullable=False)
    worker_id = db.Column(db.Integer, db.ForeignKey('worker.id'), nullable=False)