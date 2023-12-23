
import os

def checkAndCreatePath(*path):
    
    absolute_path = os.getcwd()
    
    for folder in path:
        absolute_path = os.path.join(absolute_path, folder)
        if not os.path.exists(absolute_path):
            os.mkdir(absolute_path)
    
    return absolute_path