class AdminTokenRoleException(Exception):
    def __init__(self, message='The user role of the token is invalid.'):
        self.message = message
        super().__init__(self.message)