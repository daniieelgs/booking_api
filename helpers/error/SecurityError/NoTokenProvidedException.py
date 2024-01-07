class NoTokenProvidedException(Exception):
    def __init__(self, message='No session token provided.'):
        self.message = message
        super().__init__(self.message)