from __future__ import annotations

from fastapi import APIRouter, Form, Request
from fastapi.templating import Jinja2Templates
from starlette.responses import RedirectResponse

from app.auth.security import verify_password
from app.db.users import get_user_by_username
from app.logging import get_logger

log = get_logger(__name__)
router = APIRouter()
templates = Jinja2Templates(directory="frontend/templates")


@router.get("/login")
def login_page(request: Request) -> object:
    return templates.TemplateResponse(request, "login.html", {"error": None})


@router.post("/login")
def login_submit(request: Request, username: str = Form(...), password: str = Form(...)) -> object:
    user = get_user_by_username(username)
    if user is None or not verify_password(password, user.password_hash):
        log.info("failed login attempt for username=%r", username)
        return templates.TemplateResponse(
            request, "login.html", {"error": "Incorrect username or password."}, status_code=401
        )
    request.session["user_id"] = user.id
    return RedirectResponse(url="/chat", status_code=303)


@router.post("/logout")
def logout(request: Request) -> RedirectResponse:
    request.session.clear()
    return RedirectResponse(url="/login", status_code=303)
