class ModelNotFoundException(Exception):
    def __init__(self, message=None, id = None, nameModel = None):
        self.message = message or f'{nameModel} [{id}] was not found.'
        super().__init__(self.message)