"""Pydantic schemas for request validation."""

from __future__ import annotations

from fastapi import Form
from pydantic import BaseModel, ValidationError, field_validator, model_validator


class RegisterForm(BaseModel):
    username: str
    password: str
    password_confirm: str

    @field_validator("username")
    @classmethod
    def validate_username(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Имя пользователя не может быть пустым")
        return cleaned

    @model_validator(mode="after")
    def validate_passwords(self) -> "RegisterForm":
        if self.password != self.password_confirm:
            raise ValueError("Пароли не совпадают")
        return self

    @classmethod
    def as_form(
        cls,
        username: str = Form(...),
        password: str = Form(...),
        password_confirm: str = Form(...),
    ) -> "RegisterForm":
        return cls(
            username=username,
            password=password,
            password_confirm=password_confirm,
        )


__all__ = ["RegisterForm", "ValidationError"]

