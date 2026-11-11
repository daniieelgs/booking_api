import pytest

from tests.integration.services.config_integration import db_query, redis_client

pytestmark = pytest.mark.services


def test_mariadb_is_the_production_version():
    (version,), = db_query('SELECT VERSION()')

    assert version.startswith('10.5.19'), version


def test_redis_is_the_production_version():
    info = redis_client().info('server')

    assert info['redis_version'] == '7.2.4'


def test_redis_requires_the_password():
    import redis
    from globals import REDIS_HOST, REDIS_PORT

    with pytest.raises(redis.AuthenticationError):
        redis.Redis(host=REDIS_HOST, port=int(REDIS_PORT)).ping()


def test_init_sql_created_every_table():
    tables = {row[0] for row in db_query('SHOW TABLES')}

    expected = {'api_settings', 'local', 'local_settings', 'smtp_settings', 'user_session', 'session_token', 'file',
                'weekday', 'timetable', 'work_group', 'worker', 'work_group_worker', 'service', 'status', 'booking',
                'service_booking', 'closed'}
    assert expected <= tables, expected - tables


def test_init_sql_columns_match_the_sqlalchemy_models():
    import importlib
    import pkgutil

    from db import db

    for module in pkgutil.iter_modules(['models']):
        importlib.import_module('models.' + module.name)

    real = {}
    for table, column in db_query('SELECT table_name, column_name FROM information_schema.columns WHERE table_schema = DATABASE()'):
        real.setdefault(table, set()).add(column)

    drift = {}
    for name, table in db.metadata.tables.items():
        missing = {c.name for c in table.columns} - real.get(name, set())
        if missing:
            drift[name] = sorted(missing)

    assert not drift, f'db/init.sql is missing columns that the models use: {drift}'


def test_init_sql_string_columns_are_not_shorter_than_the_models():
    import importlib
    import pkgutil

    from sqlalchemy import String

    from db import db

    for module in pkgutil.iter_modules(['models']):
        importlib.import_module('models.' + module.name)

    real = {(t, c): length for t, c, length in db_query(
        'SELECT table_name, column_name, character_maximum_length FROM information_schema.columns '
        'WHERE table_schema = DATABASE()')}

    too_short = {}
    for name, table in db.metadata.tables.items():
        for column in table.columns:
            if isinstance(column.type, String) and column.type.length and (name, column.name) in real:
                length = real[(name, column.name)]
                if length is not None and length < column.type.length:
                    too_short[f'{name}.{column.name}'] = f'db {length} < model {column.type.length}'

    assert not too_short, f'db/init.sql has shorter columns than the models: {too_short}'


def test_init_sql_created_every_trigger():
    (count,), = db_query('SELECT COUNT(*) FROM information_schema.triggers WHERE trigger_schema = DATABASE()')

    assert count == 13


def test_init_sql_seeded_lookup_tables():
    assert [r[0] for r in db_query('SELECT status FROM status ORDER BY id')] == ['P', 'C', 'D', 'X']
    assert [r[0] for r in db_query('SELECT user FROM user_session ORDER BY id')] == ['A', 'L', 'U']
    assert db_query('SELECT COUNT(*) FROM weekday') == [(7,)]
