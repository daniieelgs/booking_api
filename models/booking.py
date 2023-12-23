from db import db

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
    
    status = db.relationship('StatusModel')
    service_bookings = db.relationship('ServiceBookingModel', back_populates='booking', lazy='dynamic')
