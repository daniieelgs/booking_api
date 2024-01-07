from db import db

class UserSessionModel(db.Model):
    __tablename__ = 'user_session'
    
    id = db.Column(db.Integer, primary_key=True)
    user = db.Column(db.String(1), nullable=False, unique=True)
    name = db.Column(db.String(45))
    
    tokens = db.relationship('SessionTokenModel', back_populates='user_session')