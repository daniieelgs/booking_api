import unittest

from dbbackup.config import Config, ConfigError

REQUIRED = {'DB_NAME': 'bbdd', 'DB_USER': 'backup', 'DB_PASSWORD': 'pw'}


class TestConfig(unittest.TestCase):
    def test_defaults(self):
        cfg = Config.from_env(REQUIRED)
        self.assertEqual(cfg.db_host, 'database')
        self.assertEqual((cfg.dump_hour, cfg.dump_minute), (4, 0))
        self.assertEqual(cfg.binlog_ship_hours, 6.0)
        self.assertEqual(cfg.local_keep_dumps, 2)
        self.assertFalse(cfg.remote_enabled)

    def test_missing_required_variables_are_all_reported(self):
        with self.assertRaises(ConfigError) as ctx:
            Config.from_env({'DB_NAME': 'x'})
        self.assertIn('DB_USER', str(ctx.exception))
        self.assertIn('DB_PASSWORD', str(ctx.exception))

    def test_remote_needs_host_and_recipient(self):
        self.assertFalse(Config.from_env({**REQUIRED, 'REMOTE_HOST': 'h'}).remote_enabled)
        self.assertFalse(Config.from_env({**REQUIRED, 'AGE_RECIPIENT': 'age1x'}).remote_enabled)
        self.assertTrue(Config.from_env({**REQUIRED, 'REMOTE_HOST': 'h', 'AGE_RECIPIENT': 'age1x'}).remote_enabled)

    def test_overrides_and_types(self):
        cfg = Config.from_env({**REQUIRED, 'DUMP_HOUR': '5', 'DUMP_MINUTE': '30', 'BINLOG_SHIP_HOURS': '0.5',
                               'REMOTE_PORT': '2222', 'LOCAL_KEEP_DUMPS': '3'})
        self.assertEqual((cfg.dump_hour, cfg.dump_minute, cfg.remote_port, cfg.local_keep_dumps), (5, 30, 2222, 3))
        self.assertEqual(cfg.binlog_ship_hours, 0.5)

    def test_invalid_values_are_rejected(self):
        for var, value in [('DUMP_HOUR', '24'), ('DUMP_HOUR', 'abc'), ('DUMP_MINUTE', '60'),
                           ('REMOTE_PORT', '0'), ('BINLOG_SHIP_HOURS', '0'), ('LOCAL_KEEP_DUMPS', '0')]:
            with self.subTest(var=var, value=value):
                with self.assertRaises(ConfigError):
                    Config.from_env({**REQUIRED, var: value})

    def test_directories_derive_from_backup_dir(self):
        cfg = Config.from_env({**REQUIRED, 'BACKUP_DIR': '/data'})
        self.assertEqual(str(cfg.dumps_dir).replace('\\', '/'), '/data/dumps')
        self.assertEqual(str(cfg.binlogs_dir).replace('\\', '/'), '/data/binlogs')
        self.assertEqual(str(cfg.state_dir).replace('\\', '/'), '/data/state')


class TestSandboxHeader(unittest.TestCase):
    def test_only_a_leading_sandbox_line_is_removed(self):
        from dbbackup.util import strip_sandbox_header
        hdr = b'/*M!999999\\- enable the sandbox mode */\n'
        self.assertEqual(strip_sandbox_header(hdr + b'-- MariaDB dump\n'), b'-- MariaDB dump\n')
        self.assertEqual(strip_sandbox_header(b'-- MariaDB dump\n' + hdr), b'-- MariaDB dump\n' + hdr)
        self.assertEqual(strip_sandbox_header(b'SELECT 1;\n'), b'SELECT 1;\n')
