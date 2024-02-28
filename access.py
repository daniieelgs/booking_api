import argparse
import datetime
import json
import os
import uuid
import jwt
import mysql.connector
import sqlite3
import pyperclip

DATABASE_NAME_ENV = 'DATABASE_NAME'
DATABASE_USER_ENV = 'DATABASE_USER'
DATABASE_PASS_ENV = 'DATABASE_PASS'
DATABASE_HOST_ENV = 'DATABASE_HOST'
DATABASE_PORT_ENV = 'DATABASE_PORT'
ADMIN_IDENTITY_ENV = 'ADMIN_IDENTITY'
ADMIN_ROLE_ENV = 'ADMIN_ROLE'
SECRET_JWT_ENV = 'SECRET_JWT'
JWT_ALGORITHM_ENV = 'JWT_ALGORITHM'

class Access:
    
    def __init__(self, db_sqlite = None, **kwargs):
        
        self.user_db = kwargs.get(DATABASE_USER_ENV)
        self.password_db = kwargs.get(DATABASE_PASS_ENV)
        self.host_db = kwargs.get(DATABASE_HOST_ENV)
        self.port_db = kwargs.get(DATABASE_PORT_ENV)
        self.database_db = kwargs.get(DATABASE_NAME_ENV) 
        self.admin_identity = kwargs.get(ADMIN_IDENTITY_ENV)
        self.admin_role = kwargs.get(ADMIN_ROLE_ENV)
        self.secret_jwt = kwargs.get(SECRET_JWT_ENV)
        self.jwt_algorithm = kwargs.get(JWT_ALGORITHM_ENV)
        self.db_sqlite = db_sqlite

        required_fields = [ADMIN_IDENTITY_ENV, ADMIN_ROLE_ENV, SECRET_JWT_ENV, JWT_ALGORITHM_ENV]

        if not db_sqlite:
            required_fields += [DATABASE_USER_ENV, DATABASE_PASS_ENV, DATABASE_HOST_ENV, DATABASE_PORT_ENV, DATABASE_NAME_ENV]
            
        for k in required_fields:
            if not kwargs.get(k):
                raise ValueError(f'Missing "{k}" value.')

    def connectToDB(self):
        config = {
            'user': self.user_db,
            'password': self.password_db,
            'host': self.host_db,
            'port': self.port_db,
            'database': self.database_db,
            'raise_on_warnings': True,
        }

        return mysql.connector.connect(**config) if self.db_sqlite is None else sqlite3.connect(self.db_sqlite)

    def makeToken(self, db, exp, name = None, copy_on_clipboard = True):
        
        payload = {
            'token': uuid.uuid4().hex,
            'exp': datetime.datetime.utcnow() + datetime.timedelta(days=exp),
            'sub': self.admin_identity
        }
            
        token = jwt.encode(payload, self.secret_jwt, algorithm=self.jwt_algorithm)
            
        cursor = db.cursor()
        cursor.execute(f"SELECT id FROM user_session WHERE user = '{self.admin_role}'")
        user_session_id = cursor.fetchone()[0]

        cursor = db.cursor()
        cursor.execute(f"INSERT INTO session_token (id, jti, user_session_id, name) VALUES ('{payload['token']}', '{jwt.decode(token, key=self.secret_jwt, algorithms=[self.jwt_algorithm]).get('jti') }', '{user_session_id}', '{name}')")
        db.commit()

        try:
            if copy_on_clipboard: pyperclip.copy(token)
        except:
            pass
        
        return token

    def deleteToken(self, db, token = None, id = None):
        
        if not token and not id:
            raise ValueError('Token or ID is required.')
        
        if not id:
            id = jwt.decode(token, key=self.secret_jwt, algorithms=[self.jwt_algorithm]).get('token')
        
        cursor = db.cursor()
        cursor.execute(f"DELETE FROM session_token WHERE id = '{id}'")
        db.commit()
        
    def deleteAllTokens(self, db):
        cursor = db.cursor()
        cursor.execute(f"DELETE FROM session_token WHERE user_session_id = (SELECT id FROM user_session WHERE user = '{self.admin_role}')")
        db.commit()
    
    def list(self, db, name = None):
        cursor = db.cursor()
        query = f"SELECT name, id FROM session_token WHERE user_session_id = (SELECT id FROM user_session WHERE user = '{self.admin_role}')"
        
        if name:
            query += f" AND name LIKE '%{name}%'"
        
        cursor.execute(query)
        tokens = cursor.fetchall()
        print(f'Name{" "*30}ID')
        for token in tokens:
            print(f'{" -" if token[0] is None else token[0]}{" "*(30 - (2 if token[0] is None else len(token[0])))}{token[1]}')
        db.commit()
        return len(tokens)
    
def str_to_dict(str_arg):
    items = str_arg.split(',')
    dict_arg = {}
    for item in items:
        key, value = item.split('=')
        dict_arg[key.upper()] = value
    return dict_arg
    
def showHelp():
    print('Usage: access.py [OPTIONS]\n')
    print('Options:')
    print('  --generate <INTEGER>            Generate admin access with X days to expire.')
    print('  --name <TEXT>                   Name of the admin token. Default: current date and time. List of tokens will be shown with this name.')
    print('  --list                          List all tokens data.')
    print('  --remove-id <ID>                Remove admin access with token.')
    print('  --remove <TOKEN                 Remove admin access with token.')
    print('  --remove-all                    Remove all admin access.')
    print('  --env <file_name?|Default:.env> Load environment data file. Optional: specify .env file name.')
    print('  --help                          Show this message and exit.')

def main():
    
    
    parser = argparse.ArgumentParser(description='Generate and remove admin access.')

    parser.add_argument('--generate', type=int, help='Generate admin access with X days to expire.')
    parser.add_argument('--name', type=str, default=datetime.datetime.now().strftime("%Y-%m-%d-%H-%M-%S"), help='Name of the admin token.')
    parser.add_argument('--list', nargs='?', const=True, default=False, help='List all tokens data.')
    parser.add_argument('--remove-id', type=str, help='Remove admin access with token.')
    parser.add_argument('--remove', type=str, help='Remove admin access with token.')
    parser.add_argument('--remove-all', action='store_true', help='Remove all admin access.')
    parser.add_argument('--env', nargs='?', const=True, default=False, help='Load environment data file. Optional: specify .env file name.')
    parser.add_argument('--data', type=str_to_dict, default={}, help='Load inline data. Format: key1=value1,key2=value2')

    args = parser.parse_args()

    db = None
    
    try:
        
        DATABASE_NAME = None
        DATABASE_USER = None
        DATABASE_PASS = None
        DATABASE_HOST = None
        DATABASE_PORT = None
        ADMIN_IDENTITY = None
        ADMIN_ROLE = None
        SECRET_JWT = None
        JWT_ALGORITHM = None 
        
        if args.env is not False:
            
            from dotenv import load_dotenv
            env_path = '.env' if args.env is True else args.env
            load_dotenv(env_path)
            DATABASE_NAME = os.getenv(DATABASE_NAME_ENV)
            DATABASE_USER = os.getenv(DATABASE_USER_ENV)
            DATABASE_PASS = os.getenv(DATABASE_PASS_ENV)
            DATABASE_HOST = os.getenv(DATABASE_HOST_ENV)
            DATABASE_PORT = os.getenv(DATABASE_PORT_ENV)
            ADMIN_IDENTITY = os.getenv(ADMIN_IDENTITY_ENV)
            ADMIN_ROLE = os.getenv(ADMIN_ROLE_ENV)
            SECRET_JWT = os.getenv(SECRET_JWT_ENV)
            JWT_ALGORITHM = os.getenv(JWT_ALGORITHM_ENV)  
                
        else:
            try:
                from globals import ADMIN_IDENTITY, DATABASE_HOST, DATABASE_NAME, DATABASE_PASS, DATABASE_PORT, ADMIN_ROLE, DATABASE_USER, SECRET_JWT, JWT_ALGORITHM
            except ModuleNotFoundError:
                if not args.data or len(args.data.keys()) == 0: 
                    print('Error: No environment data found. Use --env <file_name | Default: .env> option.')
                    exit(1)

        data = {
            DATABASE_NAME_ENV: DATABASE_NAME,
            DATABASE_USER_ENV: DATABASE_USER,
            DATABASE_PASS_ENV: DATABASE_PASS,
            DATABASE_HOST_ENV: DATABASE_HOST,
            DATABASE_PORT_ENV: DATABASE_PORT,
            ADMIN_IDENTITY_ENV: ADMIN_IDENTITY,
            ADMIN_ROLE_ENV: ADMIN_ROLE,
            SECRET_JWT_ENV: SECRET_JWT,
            JWT_ALGORITHM_ENV: JWT_ALGORITHM
        }
        
        if args.data:
            data.update(args.data)
        access = Access(**data)
        
        db = access.connectToDB()
            
        if args.generate:
            print(f"{args.name}:", access.makeToken(db, args.generate, args.name))
        elif args.remove_id:
            access.deleteToken(db, id = args.remove_id)
            print('Token removed.')
        elif args.remove:
            access.deleteToken(db, token = args.remove)
            print('Token removed.')
        elif args.remove_all:
            access.deleteAllTokens(db)
            print('All tokens removed.')
        elif args.list:
            total = access.list(db, None if args.list is True else args.list)
            print('\nTokens listed. Total:', total)
        else:
            showHelp()
            print('No argument given.')
            
    except (mysql.connector.Error, ValueError) as err:
        print(f'Error: {err}')

    finally:
        if db and db.is_connected():
            db.close()
            print('Connection closed.')

if __name__ == '__main__':
    main()
    