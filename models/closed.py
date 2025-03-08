from db import db

class ClosedModel(db.Model):
     __tablename__ = 'closed'
     
     id = db.Column(db.Integer, primary_key=True)
     
     datetime_init = db.Column(db.DateTime, nullable=False)
     datetime_end = db.Column(db.DateTime, nullable=False)
     description = db.Column(db.String(255), nullable=True)
     local_id = db.Column(db.String(32), db.ForeignKey('local.id'), nullable=False)
     
     local = db.relationship('LocalModel', back_populates='closed')
     
     def __str__(self):
         return f"{self.id} - {self.datetime_init} - {self.datetime_end}"
     