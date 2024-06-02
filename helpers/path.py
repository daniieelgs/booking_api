
import os
import shutil

from dotenv import load_dotenv

from globals import ALLOWED_EXTENSIONS, IMAGE_TYPE_GALLERY, IMAGE_TYPE_LOGOS, IMAGES_FOLDER, PAGES_FOLDER, log


def checkAndCreatePath(*path):
    
    absolute_path = os.getcwd()
    
    for folder in path:
        absolute_path = os.path.join(absolute_path, folder)
        if not os.path.exists(absolute_path):
            os.mkdir(absolute_path)
    
    return absolute_path

def createPathFromLocal(local_id, _uuid = None):
    
    load_dotenv()

    PUBLIC_FOLDER = os.getenv('PUBLIC_FOLDER', None)
    p = checkAndCreatePath(PUBLIC_FOLDER, local_id, IMAGES_FOLDER, IMAGE_TYPE_LOGOS)
    log(f"'{p}' created.", uuid=_uuid)
    p = checkAndCreatePath(PUBLIC_FOLDER, local_id, IMAGES_FOLDER, IMAGE_TYPE_GALLERY)
    log(f"'{p}' created.", uuid=_uuid)
    p = checkAndCreatePath(PUBLIC_FOLDER, local_id, PAGES_FOLDER)
    log(f"'{p}' created.", uuid=_uuid)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def generateImagePath(filename, type):
    return os.path.join(IMAGES_FOLDER, type, filename).replace('\\', '/')

def generatePagePath(filename):
    return os.path.join(PAGES_FOLDER, filename).replace('\\', '/')

def saveFile(file, path, local_id, update_if_conflict = False):
    
    load_dotenv()

    PUBLIC_FOLDER = os.getenv('PUBLIC_FOLDER', None)
    
    absolute_path = os.getcwd()
    
    checkAndCreatePath(PUBLIC_FOLDER, local_id)
    
    path = os.path.join(absolute_path, PUBLIC_FOLDER, local_id, path)
    
    if os.path.exists(path) and not update_if_conflict:
        raise FileExistsError()
    
    file.save(os.path.join(absolute_path, PUBLIC_FOLDER, local_id, path))
    
def removeFile(local_id, path):
    
    load_dotenv()

    PUBLIC_FOLDER = os.getenv('PUBLIC_FOLDER', None)
    
    path = os.path.join(os.getcwd(), PUBLIC_FOLDER, local_id, path)
    
    os.remove(path)
    
def getFile(local_id, path):
    
    load_dotenv()

    PUBLIC_FOLDER = os.getenv('PUBLIC_FOLDER', None)
    
    path = os.path.join(os.getcwd(), PUBLIC_FOLDER, local_id, path)
    
    with open(path, 'rb') as f:
        file = f.read()
        
        return file
       
def removePath(local_id) -> str:
    
    load_dotenv()

    PUBLIC_FOLDER = os.getenv('PUBLIC_FOLDER', None)
    
    path = os.path.join(os.getcwd(), PUBLIC_FOLDER, local_id)
    
    shutil.rmtree(path)
    
    return path
    