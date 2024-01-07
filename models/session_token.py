from db import db

class SessionTokenModel(db.Model):
    __tablename__ = "session_token"
    
    id = db.Column(db.String(32), primary_key=True)
    jti = db.Column(db.String(36), unique=True, nullable=False)
    local_id = db.Column(db.Integer, db.ForeignKey('local.id'), unique=False, nullable=True)
    local = db.relationship('LocalModel', back_populates='tokens')
    datetime_created = db.Column(db.DateTime, nullable=True)
    user_session_id = db.Column(db.Integer, db.ForeignKey('user_session.id'), nullable=False)
    
    user_session = db.relationship('UserSessionModel', back_populates='tokens')