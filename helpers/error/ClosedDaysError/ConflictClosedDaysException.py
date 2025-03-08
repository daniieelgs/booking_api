from helpers.error.ClosedDaysError.ClosedDayException import ClosedDayException


class ConflictClosedDaysException(ClosedDayException):
    def __init__(self, msg = 'Conflict between closed days'):
        super().__init__(msg)