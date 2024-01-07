class BookingsConflictException(Exception):
    def __init__(self, message='There are bookings at this time.'):
        self.message = message
        super().__init__(self.message)