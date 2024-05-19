from datetime import time
import subprocess
import os
import mysql.connector
from mysql.connector.cursor import MySQLCursor
import redis

from globals import MAX_TIMEOUT_WAIT_BOOKING, REDIS_HOST, REDIS_PORT, is_redis_test_mode

class DatabaseConnection():
    
    def __init__(self, db_name, db_user, db_host, db_port, db_passwd):
        self.name = db_name
        self.user = db_user
        self.host = db_host
        self.port = db_port
        self.password = db_passwd

cache_memory = {}
cache_expiry_time = {}

def export_database(db: DatabaseConnection, output_file):
    os.environ['MYSQL_PWD'] = db.password
    
    try:
        command = f"mysqldump -u {db.user} -h {db.host} -P {str(db.port)} {db.name} > {output_file}"
        subprocess.run(
            command,
            check=True,
            shell=True,
            text=True,
        )
        print("La base de datos ha sido exportada exitosamente.")
    except subprocess.CalledProcessError as e:
        print("Error al exportar la base de datos:", e)
    finally:
        del os.environ['MYSQL_PWD']
       
def import_database(db: DatabaseConnection, input_file):
    os.environ['MYSQL_PWD'] = db.password
    
    try:
        print("Importando estructura y datos desde el archivo SQL...")
        command = f"mysql -u {db.user} -h {db.host} -P {db.port} {db.name} < {input_file}"
        subprocess.run(command, shell=True, check=True)
        print("Importación completada con éxito.")
    except subprocess.CalledProcessError as e:
        print("Error al importar la base de datos:", e)
    finally:
        del os.environ['MYSQL_PWD']
    
def database_exists(db: DatabaseConnection):
    cnx = mysql.connector.connect(user=db.user, password=db.password,
                                  host=db.host, port=db.port)
    cursor = cnx.cursor()
    cursor.execute(f"SHOW DATABASES LIKE '{db.name}';")
    resultado = cursor.fetchone()
    
    return resultado is not None


def create_database(db: DatabaseConnection, input_file = None, db_user_permissions = None):
    
    cnx = mysql.connector.connect(user=db.user, password=db.password,
                                  host=db.host, port=db.port)
    cursor = cnx.cursor()
    
    cursor.execute(f"CREATE DATABASE {db.name};")
    
    if db_user_permissions:
            cursor.execute(f"GRANT ALL PRIVILEGES ON {db.name}.* TO '{db_user_permissions}'@'%';")
            cursor.execute("FLUSH PRIVILEGES;")
            cnx.commit()
    
    if input_file:
        import_database(db, input_file)
        
def remove_database(db: DatabaseConnection):
    cnx = mysql.connector.connect(user=db.user, password=db.password,
                                  host=db.host, port=db.port)
    cursor = cnx.cursor()
    
    cursor.execute(f"DROP DATABASE {db.name};")

def create_redis_connection(host = REDIS_HOST, port = REDIS_PORT) -> redis.Redis:
    
    if is_redis_test_mode():
        print("Redis test mode activated.")
        return None
    
    return redis.Redis(host=host, port=port, db=0)

def register_key_value_cache(key, value, exp = MAX_TIMEOUT_WAIT_BOOKING, redis_connection = create_redis_connection(), pipeline = None):
    
    if is_redis_test_mode():
        cache_memory[key] = value
        cache_expiry_time[key] = time.time() + exp
        return
    
    if pipeline:
        pipeline.multi()
        pipeline.setex(key, exp, value)
        pipeline.execute()
        return
    
    with redis_connection.pipeline() as pipe:
        pipe.multi()            
        pipe.setex(key, exp, value)
        pipe.execute()
        
def get_key_value_cache(key, redis_connection = create_redis_connection(), pipeline = None):
    
    if is_redis_test_mode():
        
        exp = cache_expiry_time.get(key, None)
        if exp and exp < time.time():
            cache_memory.pop(key, None)
            cache_expiry_time.pop(key, None)
            return None
        
        return cache_memory.get(key, None)
    
    if pipeline:
        pipeline.get(key)
        return
    
    with redis_connection.pipeline() as pipe:
        pipe.multi()
        pipe.get(key)
        result = pipe.execute()
        return result[0] if result else None
    
def delete_key_value_cache(key, redis_connection = create_redis_connection(), pipeline = None):
    
    if is_redis_test_mode():
        cache_memory.pop(key, None)
        cache_expiry_time.pop(key, None)
        return
    
    if pipeline:
        pipeline.delete(key)
        return
    
    with redis_connection.pipeline() as pipe:
        pipe.multi()
        pipe.delete(key)
        pipe.execute()