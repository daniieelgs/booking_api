# Resource template (adapt names; keep the project's style)

```python
from flask.views import MethodView
from flask_smorest import Blueprint, abort
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
import traceback

from db import addAndCommit, deleteAndCommit, rollback
from globals import DEBUG
from models import ThingModel
from models.local import LocalModel
from schema import ThingSchema, ThingListSchema

blp = Blueprint('thing', __name__, description='CRUD de things.')


@blp.route('')
class ThingCollection(MethodView):

    @blp.response(200, ThingListSchema)
    @jwt_required(refresh=True)
    def get(self):
        """
        Devuelve los things del local identificado con el token de refresco.
        """
        things = list(LocalModel.query.get_or_404(get_jwt_identity()).things)
        return {'things': things, 'total': len(things)}

    @blp.arguments(ThingSchema)
    @blp.response(409, description='El nombre ya está en uso.')
    @blp.response(201, ThingSchema)
    @jwt_required(refresh=True)
    def post(self, data):
        """
        Crea un thing en el local identificado con el token de refresco.
        """
        thing = ThingModel(**data)
        thing.local_id = get_jwt_identity()
        try:
            addAndCommit(thing)
        except IntegrityError:
            traceback.print_exc()
            rollback()
            abort(409, message='The name is already in use.')
        except SQLAlchemyError as e:
            traceback.print_exc()
            rollback()
            abort(500, message=str(e) if DEBUG else 'Could not create the thing.')
        return thing


@blp.route('/<int:thing_id>')
class ThingByID(MethodView):

    @blp.response(404, description='El thing no existe.')
    @blp.response(403, description='No tienes permiso para ver este thing.')
    @blp.response(200, ThingSchema)
    @jwt_required(refresh=True)
    def get(self, thing_id):
        """
        Devuelve un thing por ID.
        """
        thing = ThingModel.query.get_or_404(thing_id)
        if thing.local_id != get_jwt_identity():      # ownership: always
            abort(403, message='You are not allowed to see this thing.')
        return thing
```

Register in `app.py`:

```python
from resources.thing import blp as ThingBlueprint
api.register_blueprint(ThingBlueprint, url_prefix=getApiPrefix('thing'))
```

Integration test skeleton (`tests/integration/test_<domain>.py`): copy the fixture from `tests/integration/test_work_group.py` (`create_app`, `setUp` with `db.create_all()` + `config_test.config(db=db)`, `tearDown`), create two locals through the admin token, and assert: no token → 401, owner → 200/201, other local's token → 403, unknown id → 404, duplicate → 409, bad body → 422.
