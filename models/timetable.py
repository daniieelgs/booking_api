from db import db

class TimetableModel(db.Model):
    __tablename__ = 'timetable'

    id = db.Column(db.Integer, primary_key=True)
    opening_time = db.Column(db.Time, nullable=False)
    closing_time = db.Column(db.Time, nullable=False)
    description = db.Column(db.Text, nullable=False)
    local_id = db.Column(db.String(32), db.ForeignKey('local.id'), nullable=False)
    weekday_id = db.Column(db.Integer, db.ForeignKey('weekday.id'), nullable=False)

    local = db.relationship('LocalModel', backref='timetables', lazy='dynamic')
    weekday = db.relationship('WeekdayModel', backref='timetables', lazy=True)
