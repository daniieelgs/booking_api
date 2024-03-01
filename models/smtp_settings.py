from db import db

class SmtpSettingsModel(db.Model):
    __tablename__ = "smtp_settings"
    
    id = db.Column(db.Integer, primary_key=True)
    local_settings_id = db.Column(db.Integer, db.ForeignKey('local_settings.id', ondelete='CASCADE'), nullable=False)
    name = db.Column(db.String(100), unique=True, nullable=False)
    host = db.Column(db.String(100), unique=False, nullable=False)
    port = db.Column(db.Integer, unique=False, nullable=False)
    user = db.Column(db.String(100), unique=False, nullable=False)
    password = db.Column(db.String(500), unique=False, nullable=False)
    priority = db.Column(db.Integer, unique=False, nullable=False)
    send_per_day = db.Column(db.Integer, unique=False, nullable=False)
    send_per_month = db.Column(db.Integer, unique=False, nullable=False)
    max_send_per_day = db.Column(db.Integer, unique=False, nullable=True)
    max_send_per_month = db.Column(db.Integer, unique=False, nullable=True)
    reset_send_per_day = db.Column(db.DateTime, unique=False, nullable=True)
    reset_send_per_month = db.Column(db.DateTime, unique=False, nullable=True)
    datetime_created = db.Column(db.DateTime, unique=False, nullable=False)
    datetime_updated = db.Column(db.DateTime, unique=False, nullable=False)
    
    local_settings = db.relationship(
        'LocalSettingsModel', 
        back_populates='smtp_settings'
    )
    
    __table_args__ = (db.UniqueConstraint('local_settings_id', 'priority', name='priority'),)
    
    
    