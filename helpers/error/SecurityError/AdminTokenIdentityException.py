class AdminTokenIdentityException(Exception):
    def __init__(self, message='The identity of the token is invalid.'):
        self.message = message
        super().__init__(self.message)