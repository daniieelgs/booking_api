"""Minimal DB-backed fixture for unit tests: a bare Flask app (no blueprints, no HTTP) with an in-memory SQLite and JWT.

Not `flask_testing` and not `create_app()`: just enough for helpers that talk to `db.session` or create JWTs.
"""
import unittest

from flask import Flask
from flask_jwt_extended import JWTManager
from sqlalchemy.pool import StaticPool

# every model must be imported before create_all()
import models.booking  # noqa: F401
import models.closed  # noqa: F401
import models.file  # noqa: F401
import models.local  # noqa: F401
import models.local_settings  # noqa: F401
import models.service  # noqa: F401
import models.service_booking  # noqa: F401
import models.session_token  # noqa: F401
import models.smtp_settings  # noqa: F401
import models.status  # noqa: F401
import models.timetable  # noqa: F401
import models.user_session  # noqa: F401
import models.weekday  # noqa: F401
import models.work_group  # noqa: F401
import models.work_group_worker  # noqa: F401
import models.worker  # noqa: F401
from db import db
from globals import (ADMIN_ROLE, CANCELLED_STATUS, CONFIRMED_STATUS, DONE_STATUS, JWT_ALGORITHM, LOCAL_ROLE,
                     PENDING_STATUS, SECRET_JWT, USER_ROLE, WEEK_DAYS)
from models.status import StatusModel
from models.user_session import UserSessionModel
from models.weekday import WeekdayModel


class DbTestCase(unittest.TestCase):

    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(
            SQLALCHEMY_DATABASE_URI='sqlite://',
            SQLALCHEMY_ENGINE_OPTIONS={'poolclass': StaticPool, 'connect_args': {'check_same_thread': False}},
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
            JWT_SECRET_KEY=SECRET_JWT,
            JWT_ALGORITHM=JWT_ALGORITHM,
        )
        db.init_app(self.app)
        JWTManager(self.app)

        context = self.app.app_context()
        context.push()
        self.addCleanup(context.pop)
        db.create_all()
        self.addCleanup(db.drop_all)
        self.addCleanup(db.session.remove)
        self.seed()

    def seed(self):
        for i, (user, name) in enumerate([(ADMIN_ROLE, 'Admin'), (LOCAL_ROLE, 'Local'), (USER_ROLE, 'User')], 1):
            db.session.add(UserSessionModel(id=i, user=user, name=name))
        for i, (status, name) in enumerate([(PENDING_STATUS, 'Pending'), (CONFIRMED_STATUS, 'Confirmed'),
                                            (DONE_STATUS, 'Done'), (CANCELLED_STATUS, 'Cancelled')], 1):
            db.session.add(StatusModel(id=i, status=status, name=name))
        for i, short in enumerate(WEEK_DAYS, 1):
            db.session.add(WeekdayModel(id=i, weekday=short, name=short))
        db.session.commit()
