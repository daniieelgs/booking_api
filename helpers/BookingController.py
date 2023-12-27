

from models.booking import BookingModel
from models.local import LocalModel
from models.service import ServiceModel
from models.status import StatusModel
from models.work_group import WorkGroupModel

def getBookings(datetime_init, datetime_end, local_id, status = None):

    bookings = BookingModel.query.filter(local_id = local_id).all()

    status_ids = [StatusModel.query.filter(status = s).first().id for s in status] if status else None

    return [booking for booking in bookings if (booking.datetime_end >= datetime_init or booking.datetime <= datetime_end) and (booking.status_id in status_ids if status_ids else True)]