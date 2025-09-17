import logging
from contextlib import asynccontextmanager
from typing import Any, Dict, List

from fastapi import FastAPI, Response, Request, Form, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from sqlalchemy.exc import IntegrityError
from pydantic import ValidationError

from database import (
    authenticate_user,
    create_user,
    get_user_by_username,
    increment_coffee_count,
    init_db,
)
from schemas import RegisterForm


@asynccontextmanager
async def lifespan(_: FastAPI):
    await init_db()
    yield


app = FastAPI(lifespan=lifespan)
app.add_middleware(SessionMiddleware, secret_key="super-secret-session-key")
templates = Jinja2Templates(directory="templates")

BASE_NAV_ITEMS = [
    {"id": "home", "label": "Главная", "endpoint": "home"},
    {"id": "catalog", "label": "Каталог", "endpoint": "catalog"},
    {"id": "about", "label": "О проекте", "endpoint": "about"},
    {"id": "login", "label": "Войти", "endpoint": "login"},
    {"id": "register", "label": "Регистрация", "endpoint": "register"},
]




def render_page(
    request: Request,
    template_name: str,
    active_page: str,
    context: Dict[str, Any] | None = None,
):
    user = request.session.get("user")
    nav: List[Dict[str, str]] = []
    for item in BASE_NAV_ITEMS:
        if user and item["id"] in {"login", "register"}:
            continue
        nav.append(
            {
                "id": item["id"],
                "label": item["label"],
                "url": request.url_for(item["endpoint"]),
            }
        )
    if user:
        nav.append(
            {
                "id": "logout",
                "label": "Выйти",
                "url": request.url_for("logout"),
            }
        )

    data: Dict[str, Any] = {
        "request": request,
        "nav": nav,
        "active_page": active_page,
        "user": user,
        "flash": request.session.pop("flash", None),
    }
    if context:
        data.update(context)
    return templates.TemplateResponse(request, template_name, data)


@app.get("/", name="home")
async def root(request: Request):
    return render_page(request, "index.html", "home")


@app.get("/catalog", name="catalog")
async def catalog(request: Request):
    return render_page(request, "catalog.html", "catalog")


@app.get("/about", name="about")
async def about(request: Request):
    return render_page(request, "about.html", "about")


@app.get("/login", name="login")
async def login_form(request: Request):
    error = request.session.pop("login_error", None)
    context: Dict[str, Any] = {}
    if error:
        context["error"] = error
    user = request.session.get("user")
    if user:
        context["info"] = f"Вы уже вошли как {user['username']}"
    return render_page(request, "login.html", "login", context)


@app.post("/login")
async def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
):
    user = await authenticate_user(username, password)
    if user:
        request.session["user"] = {"id": user["id"], "username": user["username"]}
        request.session["flash"] = "Вы успешно вошли"
        return RedirectResponse(request.url_for("home"), status_code=status.HTTP_303_SEE_OTHER)

    request.session["login_error"] = "Неверное имя пользователя или пароль"
    return RedirectResponse(request.url_for("login"), status_code=status.HTTP_303_SEE_OTHER)


@app.get("/register", name="register")
async def register_form(request: Request):
    error = request.session.pop("register_error", None)
    context: Dict[str, Any] = {}
    user = request.session.get("user")
    if error:
        context["error"] = error
    if user:
        context["info"] = f"Вы уже вошли как {user['username']}"
    return render_page(request, "register.html", "register", context)


@app.post("/register")
async def register_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    password_confirm: str = Form(...),
):
    username = username.strip()
    if password != password_confirm:
        request.session["register_error"] = "Пароли не совпадают"
        return RedirectResponse(request.url_for("register"), status_code=status.HTTP_303_SEE_OTHER)

    if not username:
        request.session["register_error"] = "Имя пользователя не может быть пустым"
        return RedirectResponse(request.url_for("register"), status_code=status.HTTP_303_SEE_OTHER)

    existing_user = await get_user_by_username(username)
    if existing_user:
        request.session["register_error"] = "Пользователь с таким именем уже существует"
        return RedirectResponse(request.url_for("register"), status_code=status.HTTP_303_SEE_OTHER)

    try:
        new_user = await create_user(username, password)
    except IntegrityError:
        request.session["register_error"] = "Не удалось создать пользователя"
        return RedirectResponse(request.url_for("register"), status_code=status.HTTP_303_SEE_OTHER)

    request.session["user"] = {"id": new_user.id, "username": new_user.username}
    request.session["flash"] = "Регистрация прошла успешно"
    return RedirectResponse(request.url_for("home"), status_code=status.HTTP_303_SEE_OTHER)


@app.get("/logout", name="logout")
async def logout(request: Request):
    request.session.pop("user", None)
    request.session["flash"] = "Вы вышли из аккаунта"
    return RedirectResponse(request.url_for("home"), status_code=status.HTTP_303_SEE_OTHER)


@app.get("/hello/{name}")
async def say_hello(name: str):
    return {"message": f"Hello {name}"}


@app.get("/coffee")
async def coffee(request: Request):
    user_session = request.session.get("user")
    if user_session:
        try:
            await increment_coffee_count(user_session["id"])
            logging.info(
                "Incremented coffee count for user %s", user_session.get("username")
            )
        except Exception:  # pragma: no cover - defensive logging
            logging.exception("Failed to increment coffee count")
    return Response(status_code=418)
