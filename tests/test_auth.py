
import pytest

from app import create_app
from models import db, User


@pytest.fixture
def app():
    application = create_app()
    application.config.update(
        TESTING=True,
        WTF_CSRF_ENABLED=False,
        SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
        SECRET_KEY="test-secret"
    )

    with application.app_context():
        db.create_all()
        user = User(name="Test Patient", email="patient@example.com", role="patient")
        user.set_password("TestPassword123")
        db.session.add(user)
        db.session.commit()

        yield application

        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def test_login_page_loads(client):
    response = client.get("/login")
    assert response.status_code == 200


def test_registration_page_loads(client):
    response = client.get("/register")
    assert response.status_code == 200


def test_invalid_login_is_rejected(client):
    response = client.post("/login", data={
        "email": "patient@example.com",
        "password": "wrong-password"
    }, follow_redirects=True)

    assert response.status_code == 200
    assert b"Invalid email or password" in response.data
