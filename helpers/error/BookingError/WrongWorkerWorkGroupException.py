class WrongWorkerWorkGroupException(Exception):
    def __init__(self, message='The worker must be from the same work group that the services.'):
        self.message = message
        super().__init__(self.message)