from sqlalchemy import UniqueConstraint
from db import db

class ImageModel(db.Model):
    __tablename__ = "image"
    
    id = db.Column(db.Integer, primary_key=True)
    local_id = db.Column(db.Integer, db.ForeignKey('local.id'), unique=False, nullable=False)
    local = db.relationship('LocalModel', back_populates='images')
    name = db.Column(db.String(300), nullable=False)
    type = db.Column(db.String(45), nullable=False)
    mimetype = db.Column(db.String(45), nullable=False)
    filename = db.Column(db.String(300), nullable=False, unique=True)

    __table_args__ = (UniqueConstraint('name', 'local_id', 'type', name='name'),)    
