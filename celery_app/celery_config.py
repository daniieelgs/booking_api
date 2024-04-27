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
    celery.set_default()
    app.extensions['celery'] = celery
            
    return celery
