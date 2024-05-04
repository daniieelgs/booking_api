import subprocess
import os
import mysql.connector
from mysql.connector.cursor import MySQLCursor

class DatabaseConnection():
    
    def __init__(self, db_name, db_user, db_host, db_port, db_passwd):
        self.name = db_name
        self.user = db_user
        self.host = db_host
        self.port = db_port
        self.password = db_passwd

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