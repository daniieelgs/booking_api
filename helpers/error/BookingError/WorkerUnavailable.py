class WorkerUnavailableException(Exception):
    def __init__(self, message='The worker is not available.'):
        self.message = message
        super().__init__(self.message)