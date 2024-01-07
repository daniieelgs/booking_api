from helpers.error.ModelNotFoundException import ModelNotFoundException

class StatusNotFoundException(ModelNotFoundException):
    def __init__(self, message=None, id = None):
        super().__init__(message, id=id, nameModel='Status')