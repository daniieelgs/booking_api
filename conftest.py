import os

# globals.py binds DEBUG at import time and is_*_test_mode() only honour REDIS/EMAIL_TEST_MODE when DEBUG is on,
# so the suite must not depend on a developer's local .env to get FLASK_DEBUG=1.
os.environ.setdefault('FLASK_DEBUG', '1')
