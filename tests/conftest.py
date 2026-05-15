import tempfile

import pytest
from app import create_app
from app.models import db as _db, User, Beat


class TestConfig:
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False
    SECRET_KEY = 'test-secret'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    RATELIMIT_ENABLED = False


@pytest.fixture(scope='session')
def app():
    with tempfile.TemporaryDirectory() as upload_root:
        app = create_app(TestConfig)
        app.config['UPLOAD_ROOT'] = upload_root

        @app.route('/__test__/raise-500')
        def _raise_500():
            raise RuntimeError('Intentional test error')

        with app.app_context():
            _db.create_all()
            yield app
            _db.drop_all()


@pytest.fixture(scope='function')
def client(app):
    with app.test_client() as c:
        yield c


@pytest.fixture(scope='function')
def seeded_db(app):
    """Insert one user and one beat; tears down after each test to prevent state bleed."""
    with app.app_context():
        user = User(username='testuser', email='test@example.com')
        user.set_password('testpass')
        _db.session.add(user)
        _db.session.flush()

        beat = Beat(
            title='Test Beat',
            audio_url='https://example.com/beat.mp3',
            producer_id=user.id,
            price=0.0,
        )
        _db.session.add(beat)
        _db.session.commit()
        yield {'user_id': user.id, 'beat_id': beat.id}

        _db.session.remove()
        _db.drop_all()
        _db.create_all()


def login(client, email='test@example.com', password='testpass'):
    return client.post('/login', data={'email': email, 'password': password}, follow_redirects=True)


def logout(client):
    return client.post('/logout', follow_redirects=True)
