"""Worker whose confirmation email fails the first N attempts (a simulated SMTP outage), then works.

The attempt counter lives in a file so it survives worker restarts: FLAKY_SMTP_ATTEMPTS_FILE is the file and
FLAKY_SMTP_FAIL_TIMES how many attempts raise before the real (test-mode) sender is used.
"""
import os
import smtplib

import celery_app.tasks as tasks
from tests.integration.services.worker_app import app, celery  # noqa: F401  (celery is the entrypoint object)

_real_sender = tasks.send_confirmed_booking_mail


def flaky_sender(local, booking, token, _uuid=None):
    path = os.environ['FLAKY_SMTP_ATTEMPTS_FILE']
    with open(path, 'a') as f:
        f.write('attempt\n')
    with open(path) as f:
        attempts = len(f.readlines())
    if attempts <= int(os.environ.get('FLAKY_SMTP_FAIL_TIMES', '2')):
        raise smtplib.SMTPServerDisconnected('simulated SMTP outage')
    return _real_sender(local, booking, token, _uuid=_uuid)


tasks.send_confirmed_booking_mail = flaky_sender
