class TimetableOverlapsException(Exception):
    def __init__(self, message='The new timetable overlaps with an existing one.'):
        self.message = message
        super().__init__(self.message)