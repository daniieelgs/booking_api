class PastDateException(Exception):
    def __init__(self, message='The date is in the past.'):
        self.message = message
        super().__init__(self.message)