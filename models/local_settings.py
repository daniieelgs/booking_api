from db import db

class LocalSettingsModel(db.Model):
    __tablename__ = "local_settings"
    
    id = db.Column(db.Integer, primary_key=True)
    local_id = db.Column(db.String(32), db.ForeignKey('local.id', ondelete='CASCADE'), nullable=False)
    domain = db.Column(db.String(100), unique=False, nullable=True)
    website = db.Column(db.String(300), unique=False, nullable=True)
    instagram = db.Column(db.String(100), unique=False, nullable=True)
    facebook = db.Column(db.String(100), unique=False, nullable=True)
    twitter = db.Column(db.String(100), unique=False, nullable=True)
    whatsapp = db.Column(db.String(100), unique=False, nullable=True)
    linkedin = db.Column(db.String(100), unique=False, nullable=True)
    tiktok = db.Column(db.String(100), unique=False, nullable=True)
    maps = db.Column(db.String(800), unique=False, nullable=True)
    email_contact = db.Column(db.String(70), unique=False, nullable=True)
    phone_contact = db.Column(db.String(13), unique=False, nullable=True)
    email_support = db.Column(db.String(100), unique=False, nullable=True)
    confirmation_link = db.Column(db.String(500), unique=False, nullable=True)
    cancel_link = db.Column(db.String(500), unique=False, nullable=True)
    update_link = db.Column(db.String(500), unique=False, nullable=True) 
    booking_timeout = db.Column(db.Integer, unique=False, nullable=True)
    datetime_created = db.Column(db.DateTime, unique=False, nullable=False)
    datetime_updated = db.Column(db.DateTime, unique=False, nullable=False)
    
    local = db.relationship('LocalModel', back_populates='local_settings')
    
    smtp_settings = db.relationship(
        'SmtpSettingsModel', 
        back_populates='local_settings',
        lazy='dynamic',
        cascade="all, delete"
    )
    
    