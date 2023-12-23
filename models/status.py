from db import db
import datetime

class StatusModel(db.Model):
    __tablename__ = 'status'
    
    id = db.Column(db.Integer, primary_key=True)
    status = db.Column(db.String(1), nullable=False)
    name = db.Column(db.String(45))