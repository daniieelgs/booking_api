

from datetime import datetime

import requests
from requests.auth import HTTPBasicAuth

from globals import DATABASE_HOST, DATABASE_NAME, DATABASE_PASS_ROOT, DATABASE_PORT, DATABASE_USER_ROOT, DB_BACKUP_ENDPOINT, DB_BACKUP_FOLDER, FILENAME_LOG, HOST_BACKUP_API, LOG_BACKUP_ENDPOINT, PASSWORD_BACKUP_API, USERNAME_BACKUP_API, log
from helpers.Database import DatabaseConnection, export_database

def upload_file(file_path, api_url, _uuid_log = None):
    api_url = HOST_BACKUP_API + api_url
    with open(file_path, 'r') as file:
        files = {'file': (file_path, file)}  
        response = requests.post(api_url, files=files, auth=HTTPBasicAuth(USERNAME_BACKUP_API, PASSWORD_BACKUP_API))
        if response.status_code == 201:
            log(f"Success", uuid=_uuid_log)
        else:
            log(f"Failed: {response.status_code}, {response.text}", uuid = _uuid_log)

def backup_database(_uuid_log = None):
    log('Backuping database', uuid = _uuid_log)
    log(f'Backup file: {DB_BACKUP_FOLDER}', uuid = _uuid_log)
    databse_connection = DatabaseConnection(DATABASE_NAME, DATABASE_USER_ROOT, DATABASE_HOST, DATABASE_PORT, DATABASE_PASS_ROOT)
    export_database(databse_connection, DB_BACKUP_FOLDER, _uuid_log = _uuid_log)
    upload_file(DB_BACKUP_FOLDER, DB_BACKUP_ENDPOINT, _uuid_log = _uuid_log)

def backup_logs(_uuid_log = None):
    log('Backuping logs', uuid=_uuid_log)
    yesterday = datetime.datetime.now() - datetime.timedelta(days=1)
    log_file = f'{FILENAME_LOG}.{yesterday.strftime("%Y-%m-%d")}'
    
    log('Log file:', log_file, uuid=_uuid_log)
    log('Backuping log file', uuid=_uuid_log)
    upload_file(log_file, LOG_BACKUP_ENDPOINT, _uuid_log = _uuid_log)

def backup_all(_uuid_log = None):
    
    log('Backuping', uuid=_uuid_log)
    backup_logs(_uuid_log)
    
    log('Backuping database', uuid=_uuid_log)
    backup_database(_uuid_log)
    
    log('Backuping finished', uuid=_uuid_log)