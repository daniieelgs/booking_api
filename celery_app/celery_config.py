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
    
    celery.conf.update(
        broker_connection_retry=True,
        broker_connection_retry_on_startup=True
    )
    
    celery.set_default()
    app.extensions['celery'] = celery
            
    return celery
