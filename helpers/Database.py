from datetime import time
import subprocess
import os
import mysql.connector
from mysql.connector.cursor import MySQLCursor
import redis
from redis.retry import Retry
from redis.backoff import ExponentialBackoff

from globals import MAX_TIMEOUT_WAIT_BOOKING, REDIS_HOST, REDIS_PORT, REDIS_PASSWORD, is_redis_test_mode, log

_redis_pool = None

def _get_redis_pool():
    global _redis_pool
    if _redis_pool is None and not is_redis_test_mode():
        _redis_pool = redis.ConnectionPool(
            host=REDIS_HOST,
            port=int(REDIS_PORT),
            password=REDIS_PASSWORD,
            db=0,
            socket_keepalive=True,
            socket_connect_timeout=5,
            socket_timeout=5,
            retry_on_timeout=True,
            retry=Retry(ExponentialBackoff(cap=2, base=0.1), retries=3),
            retry_on_error=[redis.ConnectionError, redis.TimeoutError],
            health_check_interval=15,
        )
    return _redis_pool

class DatabaseConnection():
    
    def __init__(self, db_name, db_user, db_host, db_port, db_passwd):
        self.name = db_name
        self.user = db_user
        self.host = db_host
        self.port = db_port
        self.password = db_passwd

        if not self.name or not self.user or not self.host or not self.port or not self.password:
            raise ValueError("DatabaseConnection: Missing required parameters")

cache_memory = {}
cache_expiry_time = {}

def export_database(db: DatabaseConnection, output_file, _uuid_log = None):
    os.environ['MYSQL_PWD'] = db.password
    
    try:
        command = f"mysqldump -u {db.user} -h {db.host} -P {str(db.port)} {db.name} > {output_file}"
        subprocess.run(
            command,
            check=True,
            shell=True,
            text=True,
        )
        log(f"Database {db.name} exported to {output_file}", uuid=_uuid_log)
        print("La base de datos ha sido exportada exitosamente.")
    except subprocess.CalledProcessError as e:
        log(f"Error exporting database", uuid=_uuid_log, level='ERROR', error=e)
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

def create_redis_connection() -> redis.Redis:

    if is_redis_test_mode():
        return None

    return redis.Redis(connection_pool=_get_redis_pool())

def ping_redis() -> bool:
    if is_redis_test_mode():
        return True
    try:
        r = create_redis_connection()
        return r is not None and r.ping()
    except Exception:
        return False

def register_key_value_cache(key, value, exp = MAX_TIMEOUT_WAIT_BOOKING, redis_connection = None, pipeline = None):

    if is_redis_test_mode():
        cache_memory[key] = value
        cache_expiry_time[key] = time.time() + exp
        return

    if redis_connection is None:
        redis_connection = create_redis_connection()

    if pipeline:
        pipeline.multi()
        pipeline.setex(key, exp, value)
        pipeline.execute()
        return

    with redis_connection.pipeline() as pipe:
        pipe.multi()
        pipe.setex(key, exp, value)
        pipe.execute()

def get_key_value_cache(key, redis_connection = None, pipeline = None):

    if is_redis_test_mode():

        exp = cache_expiry_time.get(key, None)
        if exp and exp < time.time():
            cache_memory.pop(key, None)
            cache_expiry_time.pop(key, None)
            return None

        return cache_memory.get(key, None)

    if redis_connection is None:
        redis_connection = create_redis_connection()

    if pipeline:
        pipeline.get(key)
        return

    with redis_connection.pipeline() as pipe:
        pipe.multi()
        pipe.get(key)
        result = pipe.execute()
        return result[0] if result else None

def delete_key_value_cache(key, redis_connection = None, pipeline = None):

    if is_redis_test_mode():
        cache_memory.pop(key, None)
        cache_expiry_time.pop(key, None)
        return

    if redis_connection is None:
        redis_connection = create_redis_connection()

    if pipeline:
        pipeline.delete(key)
        return

    with redis_connection.pipeline() as pipe:
        pipe.multi()
        pipe.delete(key)
        pipe.execute()