class InvalidExtensionException(Exception):
    def __init__(self, message='File extension not allowed.'):
        self.message = message
        super().__init__(self.message)