

from models.booking import BookingModel
from models.local import LocalModel
from models.service import ServiceModel
from models.status import StatusModel
from models.work_group import WorkGroupModel

def getAllLocalBookings(local_id):
    work_group = WorkGroupModel.query.filter_by(local_id=local_id).all()
    workers = [wg.workers.all() for wg in work_group]
    worker_ids = set([worker.id for worker_list in workers for worker in worker_list])
    return BookingModel.query.filter(BookingModel.worker_id.in_(worker_ids)).all()

def getBookings(local_id, datetime_init, datetime_end, status = None, worker_id = None, work_group_id = None):

    bookings = getAllLocalBookings(local_id)


    status_ids = [StatusModel.query.filter(StatusModel.status == s).first().id for s in status] if status else None

    return [booking for booking in bookings if (booking.datetime_end > datetime_init and booking.datetime < datetime_end) and (booking.status_id in status_ids if status_ids else True) and (booking.worker_id == worker_id if worker_id else True) and (booking.work_group_id == work_group_id if work_group_id else True)]