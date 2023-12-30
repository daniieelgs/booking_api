class TimetableTimesException(Exception):
    def __init__(self, message='The closing time must be later than the opening time.'):
        self.message = message
        super().__init__(self.message)