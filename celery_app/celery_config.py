from celery import Celery, Task

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

    celery.conf.update(
        broker_connection_retry=True,
        broker_connection_retry_on_startup=True,
        broker_connection_max_retries=None,
        broker_transport_options=redis_socket_options,
        result_backend_transport_options=redis_socket_options
    )
    
    celery.set_default()
    app.extensions['celery'] = celery
            
    return celery
