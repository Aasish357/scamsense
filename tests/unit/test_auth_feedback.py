from uuid import uuid4

from fastapi.testclient import TestClient

from apps.web.src.app.main import app

client = TestClient(app)


def test_register_login_and_feedback():
    username = f"testuser-{uuid4().hex[:8]}"
    email = f"{username}@example.com"
    password = 'secret'

    register = client.post(
        '/register',
        json={'username': username, 'email': email, 'password': password},
    )
    assert register.status_code == 200
    assert register.json()['msg'] == 'User registered successfully!'

    login = client.post(
        '/login',
        json={'username': username, 'password': password},
    )
    assert login.status_code == 200
    assert login.json()['msg'] == 'Login successful!'

    feedback = client.post(
        '/feedback',
        json={'username': username, 'message': 'Great tool!'},
    )
    assert feedback.status_code == 200
    assert feedback.json()['msg'] == 'Feedback submitted successfully!'
