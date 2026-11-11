"""Celery entrypoint for the test worker: `celery -A tests.integration.services.worker_app.celery worker ...`

Same app and tasks as make_celery.py, but built with ConfigIntegration so the worker never opens a real SMTP socket.
"""
from tests.integration.services.config_integration import build_app

app = build_app()
celery = app.extensions['celery']
