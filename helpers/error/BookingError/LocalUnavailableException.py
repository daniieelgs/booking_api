class LocalUnavailableException(Exception):
    def __init__(self, message='The local is not available.'):
        self.message = message
        super().__init__(self.message)