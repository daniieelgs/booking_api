from celery import Celery, Task

from globals import CELERY_VISIBILITY_TIMEOUT

def make_celery(app):
    class ContextTask(Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)
            
    celery = Celery(
        app.import_name,
        task_cls=ContextTask
    )
    
    celery.config_from_object(app.config["CELERY"])
    
    redis_socket_options = {
        'socket_keepalive': True,
        'socket_connect_timeout': 10,
        'retry_on_timeout': True,
        'health_check_interval': 30,
    }
    broker_transport_options = {**redis_socket_options, 'visibility_timeout': CELERY_VISIBILITY_TIMEOUT}

    celery.conf.update(
        broker_connection_retry=True,
        broker_connection_retry_on_startup=True,
        broker_connection_max_retries=None,
        # Acknowledge a task when it FINISHES, not when it starts: if the worker dies in the middle of an email
        # the message stays in Redis and is redelivered (an email is at-least-once, never lost).
        task_acks_late=True,
        broker_transport_options=broker_transport_options,
        result_backend_transport_options=redis_socket_options
    )
    
    celery.set_default()
    app.extensions['celery'] = celery
            
    return celery
