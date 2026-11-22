from __future__ import annotations

from typing import cast

import pytest
from starlette.requests import Request

from app.auth import dependencies as deps_module
from app.auth.dependencies import NotAuthenticatedError, redirect_to_login, require_user
from app.db.models import User


class _FakeRequest:
    """Stands in for a real Starlette Request - require_user only ever touches `.session`."""

    def __init__(self, session: dict[str, int]) -> None:
        self.session = session


def _fake_request(session: dict[str, int]) -> Request:
    return cast(Request, _FakeRequest(session))


def _user(id_: int = 1) -> User:
    return User(
        id=id_,
        username="alice",
        password_hash="x",
        display_name="Alice",
        native_lang="eng",
        target_lang="fra",
        is_absolute_beginner=False,
        email=None,
        last_proactive_sent_at=None,
        created_at="2026-01-01T00:00:00Z",
    )


def test__require_user_raises_when_no_session() -> None:
    with pytest.raises(NotAuthenticatedError):
        require_user(_fake_request({}))


def test__require_user_raises_when_session_user_no_longer_exists(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(deps_module, "get_user_by_id", lambda user_id: None)

    with pytest.raises(NotAuthenticatedError):
        require_user(_fake_request({"user_id": 1}))


def test__require_user_returns_user_when_session_valid(monkeypatch: pytest.MonkeyPatch) -> None:
    user = _user()
    monkeypatch.setattr(deps_module, "get_user_by_id", lambda user_id: user)

    assert require_user(_fake_request({"user_id": 1})) == user


def test__redirect_to_login_points_at_login_page() -> None:
    response = redirect_to_login()

    assert response.status_code == 303
    assert response.headers["location"] == "/login"
