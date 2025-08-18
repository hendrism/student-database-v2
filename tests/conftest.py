import pathlib
import sys

import pytest

sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

from app import create_app
from extensions import db
from auth.models import User


@pytest.fixture
def app():
    app = create_app('testing')
    from sqlalchemy.pool import StaticPool
    app.config.update(
        SQLALCHEMY_DATABASE_URI='sqlite://',
        SQLALCHEMY_ENGINE_OPTIONS={
            'connect_args': {'check_same_thread': False},
            'poolclass': StaticPool,
        },
    )
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def auth_header(app):
    with app.app_context():
        user = User(
            username='tester',
            email='tester@example.com',
            first_name='Test',
            last_name='User',
        )
        user.set_password('password123')
        db.session.add(user)
        db.session.commit()
        token = user.generate_access_token()
        if isinstance(token, bytes):
            token = token.decode('utf-8')
        def _verify(_token):
            return user
        User.verify_token = staticmethod(_verify)
    return {'Authorization': f'Bearer {token}'}
