from db import db

class ServiceBookingModel(db.Model):
    __tablename__ = 'service_booking'
    
    id = db.Column(db.Integer, primary_key=True)
    service_id = db.Column(db.Integer, db.ForeignKey('service.id'), nullable=False)
    booking_id = db.Column(db.Integer, db.ForeignKey('booking.id'), nullable=False)
    datetime_created = db.Column(db.DateTime, nullable=True)
    datetime_updated = db.Column(db.DateTime, nullable=True)
    
    service = db.relationship('ServiceModel', backref='service_bookings')
    booking = db.relationship('BookingModel', backref='service_bookings')