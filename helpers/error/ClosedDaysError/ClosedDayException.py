
class ClosedDayException(Exception):
    def __init__(self, message = 'The local is closed'):
        super().__init__(message)