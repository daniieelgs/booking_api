

from globals import PARAM_FILE_NAME
from helpers.error.ImageError.InvalidExtensionException import InvalidExtensionException
from helpers.error.ImageError.InvalidFilenameException import InvalidFilenameException
from helpers.error.ImageError.NotFileException import NotFileException
from helpers.path import allowed_file
from werkzeug.utils import secure_filename


def checkRequestFile(request):
    if PARAM_FILE_NAME not in request.files:
        raise NotFileException()

    file = request.files[PARAM_FILE_NAME]

    if file.filename == '':
        raise InvalidFilenameException()

    if not allowed_file(file.filename):
        raise InvalidExtensionException()

    return file, secure_filename(file.filename)