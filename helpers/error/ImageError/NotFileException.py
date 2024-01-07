class NotFileException(Exception):
    def __init__(self, message='No file provided.'):
        self.message = message
        super().__init__(self.message)