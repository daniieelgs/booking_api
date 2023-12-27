from datetime import datetime
from flask import request
from flask.views import MethodView
from flask_smorest import Blueprint, abort
from helpers.BookingController import getBookings
from models.local import LocalModel
from db import addAndFlush, addAndCommit, commit, deleteAndFlush, deleteAndCommit, flush, rollback
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy.exc import SQLAlchemyError, OperationalError
import traceback

from globals import DEBUG
from schema import PublicBookingSchema

blp = Blueprint('booking', __name__, description='Timetable CRUD')

# TODO : crear trigger que comprueba que no haya otra reserva en el mismo horario con status == C|P y con el mismo trabajador

DEFAULT_FORMAT = '%Y-%m-%d %H:%M:%S'
DEFAULT_FORMAT_DATA = '%Y-%m-%d'

@blp.route('/local/<string:local_id>')
class SeePublicBooking(MethodView):
    
    @blp.response(404, description='The local was not found')
    @blp.response(422, description='Unspecified date.')
    @blp.response(204, description='The local does not have bookings.')
    @blp.response(200, PublicBookingSchema(many=True))
    def get(self, local_id):
        """
        Retrieves public bookings from specific DateTime.
        """      
        
        date = request.args.get('date', None)
        datetime_init = request.args.get('datetime_init', None)
        datetime_end = request.args.get('datetime_end', None)
        
        try:
            if date:
                format = request.args.get('format', DEFAULT_FORMAT_DATA)
                date = datetime.strptime(date, format)
                datetime_init = datetime.combine(date, datetime.min.time())
                datetime_end = datetime.combine(date, datetime.max.time())
            elif datetime_init and datetime_end:
                format = request.args.get('format', DEFAULT_FORMAT)
                datetime_init = datetime.strptime(datetime_init, format)
                datetime_end = datetime.strptime(datetime_end, format)
            else:
                abort(422, message='Unspecified date.')
        except ValueError:
            abort(400, message='Invalid date format.')        
        
        raise getBookings(local_id, datetime_init, datetime_end, status=['C', 'P'])
    
@blp.route('/local/<string:local_id>/week')
class SeePublicBookingWeek(MethodView):
    
    def get(self, local_id):
        raise NotImplementedError()