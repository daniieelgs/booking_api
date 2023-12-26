from db import db

class WeekdayModel(db.Model):
    __tablename__ = 'weekday'

    id = db.Column(db.Integer, primary_key=True)
    weekday = db.Column(db.String(2), nullable=False)
    name = db.Column(db.String(45), nullable=False)

    timetables = db.relationship('TimetableModel', back_populates='weekday', lazy='dynamic')
