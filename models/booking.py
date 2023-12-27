from datetime import timedelta
from db import db

from sqlalchemy.orm import column_property
from sqlalchemy import select, join, text

from models.work_group import WorkGroupModel
from models.work_group_worker import WorkGroupWorkerModel
from models.worker import WorkerModel

class BookingModel(db.Model):
    __tablename__ = 'booking'
    
    id = db.Column(db.Integer, primary_key=True)
    datetime = db.Column(db.DateTime, nullable=False)
    client_name = db.Column(db.String(45))
    client_tlf = db.Column(db.String(13))
    comment = db.Column(db.Text)
    done = db.Column(db.Boolean, nullable=False)
    status_id = db.Column(db.Integer, db.ForeignKey('status.id'), nullable=False)
    datetime_created = db.Column(db.DateTime, nullable=True)
    datetime_updated = db.Column(db.DateTime, nullable=True)
    worker_id = db.Column(db.Integer, db.ForeignKey('worker.id'), nullable=False)
    
    status = db.relationship('StatusModel')
    bookings = db.relationship(
        'ServiceModel',
        secondary='service_booking',
        back_populates='bookings',
        lazy='dynamic'
    )
    worker = db.relationship('WorkerModel', back_populates='bookings', lazy='dyanmic')
    
    @property
    def local_id(self):
        
        work_group_worker = db.session.query(WorkGroupWorkerModel).filter_by(worker_id=self.worker_id).first()
        if work_group_worker:
            work_group = db.session.query(WorkGroupModel).filter_by(id=work_group_worker.work_group_id).first()
            if work_group:
                return work_group.local_id
        return None
    
    @property
    def datetime_end(self):
        total_duration = sum(service_booking.service.duration for service_booking in self.service_bookings)

        if self.datetime:
            datetime_end = self.datetime + timedelta(minutes=total_duration)
            return datetime_end
        else:
            return None
