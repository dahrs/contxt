from __future__ import annotations

from fastapi.testclient import TestClient

from app.auth.security import hash_password
from app.db.users import create_user


def _create_test_user(username: str = "alice", password: str = "testpass") -> None:
    create_user(username, hash_password(password), "Alice", "eng", "fra")


def test__login_success_redirects_to_chat(client: TestClient) -> None:
    _create_test_user()

    response = client.post("/login", data={"username": "alice", "password": "testpass"}, follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/chat"


def test__login_wrong_password_stays_on_login_page(client: TestClient) -> None:
    _create_test_user()

    response = client.post("/login", data={"username": "alice", "password": "wrong"}, follow_redirects=False)

    assert response.status_code == 401
    assert "Incorrect username or password" in response.text


def test__chat_requires_login(client: TestClient) -> None:
    response = client.get("/chat", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test__logout_clears_session(client: TestClient) -> None:
    _create_test_user()
    client.post("/login", data={"username": "alice", "password": "testpass"})

    client.post("/logout")
    response = client.get("/chat", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/login"
