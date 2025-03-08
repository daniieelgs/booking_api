from helpers.error.ClosedDaysError.ClosedDayException import ClosedDayException


class BadDatetimesClosedDaysException(ClosedDayException):
    def __init__(self, msg = 'Bad datetimes for closed days'):
        super().__init__(msg)