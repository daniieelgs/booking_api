"""Worker for the email redelivery experiments (see test_zz_email_redelivery.py).

Env:
  EXP_ATTEMPTS_FILE      one line is appended per call of the confirmation sender
  EXP_FAIL_TIMES         the first N calls raise (simulated SMTP outage), then the real test-mode sender runs
  EXP_SLOW_FIRST_SECONDS the first call sleeps this long BEFORE sending (a window to kill the worker mid-task)
  EXP_VISIBILITY_TIMEOUT Redis transport visibility_timeout in seconds (Celery default: 3600)
"""
import os
import smtplib
import time

import celery_app.tasks as tasks
from tests.integration.services.worker_app import app, celery  # noqa: F401  (celery is the entrypoint object)

_real_sender = tasks.send_confirmed_booking_mail


def experiment_sender(local, booking, token, _uuid=None):
    path = os.environ['EXP_ATTEMPTS_FILE']
    with open(path, 'a') as f:
        f.write('attempt\n')
    with open(path) as f:
        attempts = len(f.readlines())
    if attempts == 1 and float(os.environ.get('EXP_SLOW_FIRST_SECONDS', '0')) > 0:
        time.sleep(float(os.environ['EXP_SLOW_FIRST_SECONDS']))
    if attempts <= int(os.environ.get('EXP_FAIL_TIMES', '0')):
        raise smtplib.SMTPServerDisconnected('simulated SMTP outage')
    return _real_sender(local, booking, token, _uuid=_uuid)


tasks.send_confirmed_booking_mail = experiment_sender

if os.environ.get('EXP_VISIBILITY_TIMEOUT'):
    celery.conf.broker_transport_options = {**celery.conf.broker_transport_options,
                                            'visibility_timeout': int(os.environ['EXP_VISIBILITY_TIMEOUT'])}
