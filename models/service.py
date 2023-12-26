from db import db
import datetime

class ServiceModel(db.Model):
    __tablename__ = 'service'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(45), nullable=False)
    duration = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Float, nullable=False)
    work_group_id = db.Column(db.Integer, db.ForeignKey('work_group.id'), nullable=False)
    description = db.Column(db.Text)
    datetime_created = db.Column(db.DateTime, nullable=True)
    datetime_updated = db.Column(db.DateTime, nullable=True)
    
    work_group = db.relationship('WorkGroupModel', back_populates='services')
    service_bookings = db.relationship('ServiceBookingModel', back_populates='service', lazy='dynamic')
    
    def __str__(self) -> str:
        return f'ServiceModel({self.id}, {self.name}, {self.duration}, {self.price}, {self.work_group_id}, {self.description}, {self.datetime_created}, {self.datetime_updated})'