import asyncio
from fastapi.testclient import TestClient
import pytest
import uuid

from database import get_user_by_username
from main import app


@pytest.fixture()
def client():
    with TestClient(app) as client:
        yield client


def test_root(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers.get("content-type", "")
    assert "Добро пожаловать" in resp.text
    assert '<span class="nav-link nav-link--active">Главная</span>' in resp.text
    assert 'href="http://testserver/catalog"' in resp.text
    assert 'href="http://testserver/about"' in resp.text
    assert 'href="http://testserver/login"' in resp.text
    assert 'href="http://testserver/register"' in resp.text
    assert 'http://testserver/logout' not in resp.text


def test_catalog_page(client):
    resp = client.get("/catalog")
    assert resp.status_code == 200
    assert "Каталог продукции" in resp.text
    assert '<span class="nav-link nav-link--active">Каталог</span>' in resp.text
    assert 'href="http://testserver/"' in resp.text
    assert 'href="http://testserver/login"' in resp.text
    assert 'href="http://testserver/register"' in resp.text


def test_about_page(client):
    resp = client.get("/about")
    assert resp.status_code == 200
    assert "О проекте" in resp.text
    assert '<span class="nav-link nav-link--active">О проекте</span>' in resp.text
    assert 'href="http://testserver/catalog"' in resp.text
    assert 'href="http://testserver/login"' in resp.text
    assert 'href="http://testserver/register"' in resp.text


def test_login_success_flow(client):
    resp = client.post(
        "/login",
        data={"username": "admin", "password": "admin123"},
        follow_redirects=False,
    )
    assert resp.status_code == 303

    home = client.get("/")
    assert "Вы успешно вошли" in home.text
    assert "Привет, admin!" in home.text
    assert 'href="http://testserver/logout"' in home.text
    assert 'href="http://testserver/login"' not in home.text
    assert 'href="http://testserver/register"' not in home.text


def test_login_invalid_credentials(client):
    resp = client.post(
        "/login",
        data={"username": "admin", "password": "wrong"},
        follow_redirects=False,
    )
    assert resp.status_code == 303

    login_page = client.get("/login")
    assert "Неверное имя пользователя или пароль" in login_page.text
    home = client.get("/")
    assert "Привет, admin!" not in home.text


def test_register_success_flow(client):
    username = f"user_{uuid.uuid4().hex[:8]}"
    resp = client.post(
        "/register",
        data={
            "username": username,
            "password": "secret123",
            "password_confirm": "secret123",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 303

    home = client.get("/")
    assert "Регистрация прошла успешно" in home.text
    assert f"Привет, {username}!" in home.text
    assert 'href="http://testserver/logout"' in home.text


def test_register_password_mismatch(client):
    username = f"mismatch_{uuid.uuid4().hex[:8]}"
    resp = client.post(
        "/register",
        data={
            "username": username,
            "password": "secret123",
            "password_confirm": "other",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 303

    register_page = client.get("/register")
    assert "Пароли не совпадают" in register_page.text


def test_register_duplicate_username(client):
    username = f"dup_{uuid.uuid4().hex[:8]}"
    client.post(
        "/register",
        data={
            "username": username,
            "password": "secret123",
            "password_confirm": "secret123",
        },
    )

    resp = client.post(
        "/register",
        data={
            "username": username,
            "password": "secret123",
            "password_confirm": "secret123",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 303

    register_page = client.get("/register")
    assert "Пользователь с таким именем уже существует" in register_page.text


def test_logout_flow(client):
    client.post(
        "/login",
        data={"username": "admin", "password": "admin123"},
    )
    resp = client.get("/logout", follow_redirects=False)
    assert resp.status_code == 303

    home = client.get("/")
    assert "Вы вышли из аккаунта" in home.text
    assert 'href="http://testserver/logout"' not in home.text
    assert 'href="http://testserver/login"' in home.text
    assert 'href="http://testserver/register"' in home.text


def test_hello_name(client):
    name = "Alice"
    resp = client.get(f"/hello/{name}")
    assert resp.status_code == 200
    assert resp.json() == {"message": f"Hello {name}"}


def test_coffee(client):
    resp = client.get("/coffee")
    assert resp.status_code == 418
    # Endpoint intentionally returns empty body
    assert resp.text == ""


def test_coffee_increments_for_logged_in_user(client):
    pre_user = asyncio.run(get_user_by_username("admin"))
    pre_count = pre_user.coffee_count if pre_user else 0

    client.post(
        "/login",
        data={"username": "admin", "password": "admin123"},
    )

    resp = client.get("/coffee")
    assert resp.status_code == 418

    post_user = asyncio.run(get_user_by_username("admin"))
    assert post_user is not None
    assert post_user.coffee_count == pre_count + 1
