import os
import shutil

import mysql.connector
import redis

from default_config import DefaultConfig


class ConfigIntegration(DefaultConfig):
    """Real MariaDB + Redis (docker/docker-compose.test.yml); only the SMTP socket stays faked."""

    def __init__(self) -> None:
        super().__init__()
        self.public_folder = 'tests/public'
        self.waiter_booking_status = None
        self.email_test_mode = True
        self.redis_test_mode = False


def build_app():
    from app import create_app
    return create_app(ConfigIntegration())


def db_connection():
    from globals import DATABASE_HOST, DATABASE_NAME, DATABASE_PASS, DATABASE_PORT, DATABASE_USER
    return mysql.connector.connect(user=DATABASE_USER, password=DATABASE_PASS, host=DATABASE_HOST,
                                   port=int(DATABASE_PORT), database=DATABASE_NAME, autocommit=True)


def db_query(sql, params=None):
    cnx = db_connection()
    try:
        cursor = cnx.cursor()
        cursor.execute(sql, params or ())
        return cursor.fetchall()
    finally:
        cnx.close()


def db_execute(sql, params=None):
    cnx = db_connection()
    try:
        cursor = cnx.cursor()
        cursor.execute(sql, params or ())
    finally:
        cnx.close()


def delete_test_locals(local_ids=None):
    """Remove seeded locals (all FKs cascade). Without ids, also sweeps leftovers of aborted runs."""
    if local_ids:
        for local_id in local_ids:
            db_execute('DELETE FROM local WHERE id = %s', (local_id,))
    else:
        db_execute("DELETE FROM local WHERE name = 'Local-Test'")


def redis_client():
    from globals import REDIS_HOST, REDIS_PASSWORD, REDIS_PORT
    return redis.Redis(host=REDIS_HOST, port=int(REDIS_PORT), password=REDIS_PASSWORD, db=0)


def mint_admin_token():
    """Admin JWT registered in the real MariaDB (user_session seeds already come from db/init.sql)."""
    from access import Access
    from globals import (ADMIN_IDENTITY, ADMIN_ROLE, DATABASE_HOST, DATABASE_NAME, DATABASE_PASS, DATABASE_PORT,
                         DATABASE_USER, JWT_ALGORITHM, SECRET_JWT)

    access = Access(
        None,
        DATABASE_USER=DATABASE_USER, DATABASE_PASS=DATABASE_PASS, DATABASE_HOST=DATABASE_HOST,
        DATABASE_PORT=DATABASE_PORT, DATABASE_NAME=DATABASE_NAME,
        ADMIN_IDENTITY=ADMIN_IDENTITY, ADMIN_ROLE=ADMIN_ROLE, SECRET_JWT=SECRET_JWT, JWT_ALGORITHM=JWT_ALGORITHM)
    cnx = access.connectToDB()
    try:
        return access.makeToken(cnx, 1, name='services-tests', copy_on_clipboard=False)
    finally:
        cnx.close()


def remove_public_folders(local_ids):
    folder = os.getenv('PUBLIC_FOLDER', 'tests/public')
    for local_id in local_ids:
        path = os.path.join(os.getcwd(), folder, local_id)
        if os.path.exists(path):
            shutil.rmtree(path)
