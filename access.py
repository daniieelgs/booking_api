import argparse
import datetime
import uuid
import jwt
import mysql.connector
import sqlite3
import pyperclip

from globals import ADMIN_IDENTITY, DATABASE_HOST, DATABASE_NAME, DATABASE_PASS, DATABASE_PORT, ADMIN_ROLE, DATABASE_USER, SECRET_JWT, JWT_ALGORITHM

class Access:
    
    def __init__(self, user_db = DATABASE_USER, password_db = DATABASE_PASS, host_db = DATABASE_HOST, port_db = DATABASE_PORT, database_db = DATABASE_NAME, db_sqlite = None):
        self.user_db = user_db
        self.password_db = password_db
        self.host_db = host_db
        self.port_db = port_db
        self.database_db = database_db 
        self.db_sqlite = db_sqlite

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

    def makeToken(self, db, exp, copy_on_clipboard = True):
        
        payload = {
            'token': uuid.uuid4().hex,
            'exp': datetime.datetime.utcnow() + datetime.timedelta(days=exp),
            'sub': ADMIN_IDENTITY,
        }
            
        token = jwt.encode(payload, SECRET_JWT, algorithm=JWT_ALGORITHM)
            
        cursor = db.cursor()
        cursor.execute(f"SELECT id FROM user_session WHERE user = '{ADMIN_ROLE}'")
        user_session_id = cursor.fetchone()[0]

        cursor = db.cursor()
        cursor.execute(f"INSERT INTO session_token (id, jti, user_session_id) VALUES ('{payload['token']}', '{jwt.decode(token, key=SECRET_JWT, algorithms=[JWT_ALGORITHM]).get('jti') }', '{user_session_id}')")
        db.commit()

        if copy_on_clipboard: pyperclip.copy(token)
        
        return token

    def deleteToken(self, db, token):
        
        id = jwt.decode(token, key=SECRET_JWT, algorithms=[JWT_ALGORITHM]).get('token')
        
        cursor = db.cursor()
        cursor.execute(f"DELETE FROM session_token WHERE id = '{id}'")
        db.commit()
        
    def deleteAllTokens(self, db):
        cursor = db.cursor()
        cursor.execute(f"DELETE FROM session_token WHERE user_session_id = (SELECT id FROM user_session WHERE user = '{ADMIN_ROLE}')")
        db.commit()
    
def showHelp():
    print('Usage: access.py [OPTIONS]\n')
    print('Options:')
    print('  --generate INTEGER  Generate admin access with X days to expire.')
    print('  --remove TOKEN       Remove admin access with token.')
    print('  --remove-all        Remove all admin access.')
    print('  --help              Show this message and exit.')

def main():
    
    access = Access()
    
    parser = argparse.ArgumentParser(description='Generate and remove admin access.')

    parser.add_argument('--generate', type=int, help='Generate admin access with X days to expire.')
    parser.add_argument('--remove', type=str, help='Remove admin access with token.')
    parser.add_argument('--remove-all', action='store_true', help='Remove all admin access.')

    args = parser.parse_args()

    
    try:
        db = access.connectToDB()
            
        if args.generate:
            print(access.makeToken(db, args.generate))
        elif args.remove:
            access.deleteToken(db, args.remove)
            print('Token removed.')
        elif args.remove_all:
            access.deleteAllTokens(db)
            print('All tokens removed.')
        else:
            showHelp()
            print('No argument given.')
            
    except mysql.connector.Error as err:
        print(f'Error: {err}')

    finally:
        if db and db.is_connected():
            db.close()
            print('Connection closed.')

if __name__ == '__main__':
    main()
    