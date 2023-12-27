from flask import request
from flask.views import MethodView
from flask_smorest import Blueprint, abort
from models.local import LocalModel
from db import addAndFlush, addAndCommit, commit, deleteAndFlush, deleteAndCommit, flush, rollback
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy.exc import SQLAlchemyError, OperationalError
import traceback

from globals import DEBUG

blp = Blueprint('booking', __name__, description='Timetable CRUD')

# TODO : crear trigger que comprueba que no haya otra reserva en el mismo horario con status == C|P y con el mismo trabajador



@blp.route('/local/<string:local_id>')
class SeeBooking(MethodView):
    
    @blp.response(404, description='The local was not found')
    @blp.response(422, description='Unspecified date..')
    @blp.response(204, description='The local does not have bookings.')
    # @blp.response(200, TimetableSchema(many=True))
    def get(self, local_id):
        """
        Retrieves bookings from specific DateTime.
        """      
        
        date = request.args.get('date', None)
        datetime_init = request.args.get('datetime_init', None)
        datetime_end = request.args.get('datetime_end', None)
        format = request.args.get('format', None) #TODO : default format
        
        if not date and (not datetime_init or not datetime_end): abort(422, message='Unspecified date.')
        
        
        
        raise NotImplementedError()
    
@blp.route('/local/<string:local_id>/week')
class SeeBookingWeek(MethodView):
    
    def get(self, local_id):
        raise NotImplementedError()