from db import db
import datetime

class LocalModel(db.Model):
    __tablename__ = "local"
    
    id = db.Column(db.String(32), primary_key=True)
    name = db.Column(db.String(45), unique=False, nullable=False)
    tlf = db.Column(db.String(13), unique=False, nullable=False)
    email = db.Column(db.String(70), unique=True, nullable=False)
    description = db.Column(db.Text, unique=False, nullable=True)
    address = db.Column(db.String(120), unique=False, nullable=True)
    postal_code = db.Column(db.String(5), unique=False, nullable=True)
    village = db.Column(db.String(45), unique=False, nullable=True)
    province = db.Column(db.String(45), unique=False, nullable=True)
    location = db.Column(db.String(10), unique=False, nullable=False)
    password = db.Column(db.String(200), unique=False, nullable=False)
    datetime_created = db.Column(db.DateTime, unique=False, nullable=True)
    datetime_updated = db.Column(db.DateTime, unique=False, nullable=True)
    
    tokens = db.relationship('SessionTokenModel', back_populates='local', lazy='dynamic', cascade="all, delete")
    work_groups = db.relationship('WorkGroupModel', back_populates='local', lazy='dynamic', cascade="all, delete")
    
    def __str__(self):
        return (f"LocalModel(id='{self.id}', name='{self.name}', tlf='{self.tlf}', "
                f"email='{self.email}', address='{self.address}', postal_code='{self.postal_code}', "
                f"village='{self.village}', province='{self.province}', location='{self.location}', "
                f"password='{self.password}', "
                f"datetime_created='{self.datetime_created}', datetime_updated='{self.datetime_updated}')")