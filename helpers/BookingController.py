

from models.booking import BookingModel
from models.local import LocalModel
from models.service import ServiceModel
from models.status import StatusModel
from models.work_group import WorkGroupModel

def getBookings(datetime_init, datetime_end, local_id, status = None, worker_id = None, work_group_id = None):

    bookings = BookingModel.query.filter(BookingModel.local_id == local_id).all()

    status_ids = [StatusModel.query.filter(StatusModel.status == s).first().id for s in status] if status else None

    return [booking for booking in bookings if (booking.datetime_end > datetime_init and booking.datetime < datetime_end) and (booking.status_id in status_ids if status_ids else True) and (booking.worker_id == worker_id if worker_id else True) and (booking.work_group_id == work_group_id if work_group_id else True)]