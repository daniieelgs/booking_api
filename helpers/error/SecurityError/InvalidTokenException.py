class InvalidTokenException(Exception):
    def __init__(self, message='The session token is invalid.'):
        self.message = message
        super().__init__(self.message)