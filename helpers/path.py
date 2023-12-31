
import os

from dotenv import load_dotenv

from globals import ALLOWED_EXTENSIONS, IMAGE_TYPE_GALLERY, IMAGE_TYPE_LOGOS, IMAGES_FOLDER


def checkAndCreatePath(*path):
    
    absolute_path = os.getcwd()
    
    for folder in path:
        absolute_path = os.path.join(absolute_path, folder)
        if not os.path.exists(absolute_path):
            os.mkdir(absolute_path)
    
    return absolute_path

def createPathFromLocal(local_id):
    
    load_dotenv()

    PUBLIC_FOLDER = os.getenv('PUBLIC_FOLDER', None)
    checkAndCreatePath(PUBLIC_FOLDER, local_id, IMAGES_FOLDER, IMAGE_TYPE_LOGOS)
    checkAndCreatePath(PUBLIC_FOLDER, local_id, IMAGES_FOLDER, IMAGE_TYPE_GALLERY)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def savePath(file, filename, type, local_id):
    
    load_dotenv()

    PUBLIC_FOLDER = os.getenv('PUBLIC_FOLDER', None)
    
    absolute_path = os.getcwd()
    
    file.save(os.path.join(absolute_path, PUBLIC_FOLDER, local_id, IMAGES_FOLDER, type, filename))
    
def getImage(local_id, filename, type):
    
    load_dotenv()

    PUBLIC_FOLDER = os.getenv('PUBLIC_FOLDER', None)
    
    path = os.path.join(os.getcwd(), PUBLIC_FOLDER, local_id, IMAGES_FOLDER, type, filename)
    
    with open(path, 'rb') as f:
        image = f.read()
        
        return image

def removeImage(local_id, filename, type):
    
    load_dotenv()

    PUBLIC_FOLDER = os.getenv('PUBLIC_FOLDER', None)
    
    path = os.path.join(os.getcwd(), PUBLIC_FOLDER, local_id, IMAGES_FOLDER, type, filename)
    
    os.remove(path)