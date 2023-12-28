from datetime import datetime, timedelta
import random
from flask import request
from flask.views import MethodView
from flask_smorest import Blueprint, abort
from helpers.BookingController import getBookings
from helpers.TimetableController import getTimetable
from models.booking import BookingModel
from models.local import LocalModel
from db import addAndFlush, addAndCommit, commit, deleteAndFlush, deleteAndCommit, flush, rollback
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy.exc import SQLAlchemyError, OperationalError
import traceback

from globals import DEBUG, CONFIRMED_STATUS, PENDING_STATUS, WEEK_DAYS
from models.service import ServiceModel
from models.status import StatusModel
from models.weekday import WeekdayModel
from models.worker import WorkerModel
from schema import BookingSchema, PublicBookingSchema

blp = Blueprint('booking', __name__, description='Timetable CRUD')

# TODO : crear trigger que comprueba que no haya otra reserva en el mismo horario con status == C|P y con el mismo trabajador
# TODO : documentar parametro GET
# TODO : modificar estados de las reservas

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
        
        worker_id = request.args.get('worker_id', None)
        work_group_id = request.args.get('work_group_id', None)
        
        return getBookings(local_id, datetime_init, datetime_end, status=[CONFIRMED_STATUS, PENDING_STATUS], worker_id=worker_id, work_group_id=work_group_id)
    
@blp.route('/local/<string:local_id>/week')
class SeePublicBookingWeek(MethodView):
    
    @blp.response(404, description='The local was not found')
    @blp.response(422, description='Unspecified date.')
    @blp.response(204, description='The local does not have bookings.')
    @blp.response(200, PublicBookingSchema(many=True))
    def get(self, local_id):
        
        date = request.args.get('date', None)
        format = request.args.get('format', DEFAULT_FORMAT_DATA)
        
        datetime_init = None
        datetime_end = None
        
        try:
            if date:
                date = datetime.strptime(date, format)
                week_day = date.weekday()
                date = date - timedelta(days=week_day)
                datetime_init = datetime.combine(date, datetime.min.time())
                datetime_end = datetime.combine(date, datetime.max.time()) + timedelta(days=7)
            else:
                abort(422, message='Unspecified date.')
        except ValueError:
            abort(400, message='Invalid date format.')
            
        worker_id = request.args.get('worker_id', None)
        work_group_id = request.args.get('work_group_id', None)
                        
        return getBookings(local_id, datetime_init, datetime_end, status=[CONFIRMED_STATUS, PENDING_STATUS], worker_id=worker_id, work_group_id=work_group_id)
    
@blp.route('/local/<string:local_id>')
class Booking(MethodView):
    
    #TODO : comprobar timetable del local
    # TODO : comprobar que el trabajador tiene el horario disponible
    @blp.arguments(BookingSchema)
    @blp.response(404, description='The local was not found. The service was not found. The worker was not found.')
    @blp.response(400, description='Invalid date format.')
    @blp.response(409, description='There is already a booking in that time. The worker is not available. The services must be from the same work group. The worker must be from the same work group that the services. The local is not available.')
    @blp.response(201, BookingSchema)
    @jwt_required(fresh=True)
    def post(self, new_booking, local_id):
        """
        Creates a new booking.
        """
        
        local = LocalModel.query.get(local_id)
        if not local:
            abort(404, message=f'The local [{local_id}] was not found.')
        
        format = new_booking['format'] if 'format' in new_booking else DEFAULT_FORMAT
        worker_id = new_booking['worker_id'] if 'worker_id' in new_booking else None
        
        try:
            datetime_init = datetime.strptime(new_booking['datetime'], format)
        except ValueError:
            abort(400, message='Invalid date format.')
        
        total_duration = 0
        services = []
                
        for service_id in set(new_booking['services_ids']):
            service = ServiceModel.query.get(service_id)
            if not service:
                abort(404, message=f'The service [{service_id}] was not found.')
            total_duration += service.duration
            
            if len(services) > 0 and service.work_group_id != services[0].work_group_id:
                abort(409, message='The services must be from the same work group.')
                
            services.append(service)
            
        if not services:
            abort(404, message='The service was not found.')
        
        datetime_end = datetime_init + timedelta(minutes=total_duration)
                
        week_day = WeekdayModel.query.filter_by(weekday=WEEK_DAYS[datetime_init.weekday()]).first()
        
        if not week_day:
            abort(500, message='The weekday was not found.')
        
        if not getTimetable(local_id, week_day.id, datetime_init=datetime_init, datetime_end=datetime_end):
            abort(409, message='The local is not available.')
        
        if worker_id:
            worker = WorkerModel.query.get(worker_id)
            if not worker:
                abort(404, message=f'The worker [{worker_id}] was not found.')
            
            if worker.work_group_id != services[0].work_group_id:
                abort(409, message='The worker must be from the same work group that the services.')
                
            if getBookings(local_id, datetime_init, datetime_end, status=[CONFIRMED_STATUS, PENDING_STATUS], worker_id=worker_id):
                abort(409, message='The worker is not available.')
                
        else: 
            workers = list(services[0].work_group.workers.all())
            
            random.shuffle(workers)
            
            for worker in workers:
                if getBookings(local_id, datetime_init, datetime_end, status=[CONFIRMED_STATUS, PENDING_STATUS], worker_id=worker.id):
                    continue
                
                worker_id = worker.id
                break
            
            if not worker_id:
                abort(409, message='There is already a booking in that time.')
        
        status = StatusModel.query.filter_by(status=PENDING_STATUS).first()
        
        if not status:
            abort(500, message='The status was not found.')
        
        new_booking['local_id'] = local_id
        new_booking['status_id'] = status.id
        new_booking['worker_id'] = worker_id
        
        booking = BookingModel(**new_booking)
        booking.services = services
        
        try:
            addAndCommit(booking)
        except SQLAlchemyError as e:
            traceback.print_exc()
            rollback()
            abort(500, message = str(e) if DEBUG else 'Could not create the booking.')
        
        return booking