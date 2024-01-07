from db import db

class WorkerModel(db.Model):
    __tablename__ = 'worker'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(35), nullable=False)
    last_name = db.Column(db.String(70))
    email = db.Column(db.String(70))
    tlf = db.Column(db.String(13))
    image = db.Column(db.String(300))
    datetime_created = db.Column(db.DateTime, nullable=True)
    datetime_updated = db.Column(db.DateTime, nullable=True)
    
    bookings = db.relationship('BookingModel', back_populates='worker', lazy='dynamic')
    work_groups = db.relationship(
        'WorkGroupModel', 
        secondary='work_group_worker', 
        back_populates='workers',
        lazy='dynamic'
    )
    
    
