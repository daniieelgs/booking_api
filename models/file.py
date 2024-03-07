from sqlalchemy import UniqueConstraint
from db import db

class FileModel(db.Model):
    __tablename__ = "file"
    
    id = db.Column(db.Integer, primary_key=True)
    local_id = db.Column(db.Integer, db.ForeignKey('local.id'), unique=False, nullable=False)
    local = db.relationship('LocalModel', back_populates='images')
    name = db.Column(db.String(300), nullable=False)
    mimetype = db.Column(db.String(45), nullable=False)
    path = db.Column(db.String(300), nullable=False)

    __table_args__ = (UniqueConstraint('name', 'local_id', 'path', name='name'),)    
