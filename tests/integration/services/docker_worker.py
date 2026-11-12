"""A Celery worker in a Linux container (prefork + event loop, like docker-worker-1 in production).

The host-side Worker in resilience_support runs `--pool=solo` on Windows, which uses the blocking loop and does not
reproduce the Redis `visibility_timeout` redelivery.

Build the image once from the repo root (`docker build -f docker/Dockerfile.exp-worker -t booking-exp-worker .`); the
tests that use it are marked `redelivery` and are excluded from CI because each one takes minutes.
"""
import os
import subprocess
import time

from tests.integration.services.conftest import TEST_ENV

APP = 'tests.integration.services.worker_app_experiment.celery'


class DockerWorker:

    def __init__(self, name, env=None, app_path=APP):
        self.name = name
        self.app_path = app_path
        self.env = env or {}

    def start(self, wait=90):
        subprocess.run(['docker', 'rm', '-f', self.name], capture_output=True)
        env = {**TEST_ENV, 'FLASK_DEBUG': '1', **self.env}
        for key in ('DATABASE_HOST', 'REDIS_HOST'):
            env[key] = 'host.docker.internal'
        env['CELERY_BROKER_URL'] = env['CELERY_BROKER_URL'].replace('127.0.0.1', 'host.docker.internal')
        env['CELERY_RESULT_BACKEND'] = env['CELERY_RESULT_BACKEND'].replace('127.0.0.1', 'host.docker.internal')
        args = ['docker', 'run', '-d', '--name', self.name, '-v', f'{os.getcwd()}:/app', '-w', '/app',
                '--add-host', 'host.docker.internal:host-gateway', '-e', 'RUN_INTEGRATION_TESTS=1']
        for key, value in env.items():
            args += ['-e', f'{key}={value}']
        args += ['booking-exp-worker', 'celery', '-A', self.app_path, 'worker', '--loglevel=info', '-Q', 'priority,default', '--concurrency=2']
        subprocess.run(args, check=True, capture_output=True)
        deadline = time.time() + wait
        while time.time() < deadline:
            if 'ready.' in self.logs():
                return self
            time.sleep(1)
        raise RuntimeError('worker did not become ready:\n' + self.logs()[-3000:])

    def logs(self):
        out = subprocess.run(['docker', 'logs', self.name], capture_output=True, text=True)
        return out.stdout + out.stderr

    def kill(self):
        subprocess.run(['docker', 'kill', self.name], capture_output=True)

    def stop(self):
        subprocess.run(['docker', 'stop', '-t', '30', self.name], capture_output=True)

    def remove(self):
        subprocess.run(['docker', 'rm', '-f', self.name], capture_output=True)
