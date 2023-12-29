class UnspecifedDateException(Exception):
    def __init__(self, message='Unspecified date.'):
        self.message = message
        super().__init__(self.message)