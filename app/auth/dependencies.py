from __future__ import annotations

from fastapi import Request
from starlette.responses import RedirectResponse

from app.db.models import User
from app.db.users import get_user_by_id


class NotAuthenticatedError(Exception):
    """Raised by `require_user` when the request has no valid session; routes convert this to a
    redirect to the login page."""


def require_user(request: Request) -> User:
    user_id = request.session.get("user_id")
    if user_id is not None:
        user = get_user_by_id(user_id)
        if user is not None:
            return user
    raise NotAuthenticatedError()


def redirect_to_login() -> RedirectResponse:
    return RedirectResponse(url="/login", status_code=303)
