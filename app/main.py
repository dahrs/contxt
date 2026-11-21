from __future__ import annotations

from fastapi import FastAPI, Request
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import PlainTextResponse, RedirectResponse
from starlette.staticfiles import StaticFiles

from app.auth.dependencies import NotAuthenticatedError, redirect_to_login
from app.auth.routes import router as auth_router
from app.config import settings
from app.db.connection import init_db
from app.logging import get_logger
from app.routes.chat import router as chat_router

log = get_logger(__name__)

app = FastAPI(title="contxt")
app.add_middleware(SessionMiddleware, secret_key=settings.session_secret_key)
app.mount("/static", StaticFiles(directory="frontend/static"), name="static")
app.include_router(auth_router)
app.include_router(chat_router)


@app.exception_handler(NotAuthenticatedError)
def handle_not_authenticated(request: Request, exc: NotAuthenticatedError) -> object:
    return redirect_to_login()


@app.exception_handler(Exception)
def handle_unexpected_error(request: Request, exc: Exception) -> object:
    log.exception("unhandled exception on %s %s", request.method, request.url.path)
    return PlainTextResponse("Something went wrong.", status_code=500)


@app.on_event("startup")
def on_startup() -> None:
    init_db()


@app.get("/")
def root() -> object:
    return RedirectResponse(url="/chat", status_code=303)
