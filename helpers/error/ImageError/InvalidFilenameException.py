class InvalidFilenameException(Exception):
    def __init__(self, message='Invalid file name.'):
        self.message = message
        super().__init__(self.message)