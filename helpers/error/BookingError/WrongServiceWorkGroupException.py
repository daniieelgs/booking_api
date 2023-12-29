class WrongServiceWorkGroupException(Exception):
    def __init__(self, message='The services must be from the same work group.'):
        self.message = message
        super().__init__(self.message)