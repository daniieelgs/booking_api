import argparse
import datetime
import uuid
import jwt
import mysql.connector
import pyperclip

from globals import ADMIN_IDENTITY, DATABASE_HOST, DATABASE_NAME, DATABASE_PASS, DATABASE_PORT, ADMIN_ROLE, DATABASE_USER, SECRET_JWT, JWT_ALGORITHM

def mi_programa(parametro1, parametro2, opcional=None):
    # Tu lógica de programa aquí
    print(f'Parámetro 1: {parametro1}')
    print(f'Parámetro 2: {parametro2}')
    print(f'Opcional: {opcional}')

def connectToDB():
    config = {
        'user': DATABASE_USER,
        'password': DATABASE_PASS,
        'host': DATABASE_HOST,
        'port': DATABASE_PORT,
        'database': DATABASE_NAME,
        'raise_on_warnings': True,
    }

    return mysql.connector.connect(**config)

def makeToken(db, exp):
    
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

    pyperclip.copy(token)
    
    return token

def deleteToken(db, token):
    
    id = jwt.decode(token, key=SECRET_JWT, algorithms=[JWT_ALGORITHM]).get('token')
    
    cursor = db.cursor()
    cursor.execute(f"DELETE FROM session_token WHERE id = '{id}'")
    db.commit()
    
def deleteAllTokens(db):
    cursor = db.cursor()
    cursor.execute(f"DELETE FROM session_token WHERE user_session_id = (SELECT id FROM user_session WHERE user = '{ADMIN_ROLE}')")
    db.commit()

def main():
    parser = argparse.ArgumentParser(description='Generate and remove admin access.')

    parser.add_argument('--generate', type=int, help='Generate admin access with X days to expire.')
    parser.add_argument('--remove', type=str, help='Remove admin access with token.')
    parser.add_argument('--remove-all', action='store_true', help='Remove all admin access.')

    args = parser.parse_args()

    
    try:
        db = connectToDB()
            
        if args.generate:
            print(makeToken(db, args.generate))
        elif args.remove:
            deleteToken(db, args.remove)
        elif args.remove_all:
            deleteAllTokens(db)
        else:
            print('No argument given.')
            
    except mysql.connector.Error as err:
        print(f'Error: {err}')

    finally:
        # Cerrar la conexión al salir, incluso si hay un error
        if db.is_connected():
            db.close()
            print('Connection closed.')

if __name__ == '__main__':
    main()
    