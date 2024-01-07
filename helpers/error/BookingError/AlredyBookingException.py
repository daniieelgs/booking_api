class AlredyBookingExceptionException(Exception):
    def __init__(self, message='Booking not available.'):
        self.message = message
        super().__init__(self.message)