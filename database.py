"""Asynchronous database utilities for user authentication and registration."""

from __future__ import annotations

import hashlib
from typing import Optional

from sqlalchemy import Column, Integer, String, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase


DATABASE_URL = "sqlite+aiosqlite:///app.db"
DEFAULT_USERS = (
    ("admin", "admin123"),
    ("barista", "coffee42"),
)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String(64), unique=True, nullable=False, index=True)
    password_hash = Column(String(128), nullable=False)
    coffee_count = Column(Integer, nullable=False, default=0)


engine: AsyncEngine = create_async_engine(DATABASE_URL, echo=False, future=True)
async_session: async_sessionmaker[AsyncSession] = async_sessionmaker(
    engine, expire_on_commit=False
)


def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        result = await conn.exec_driver_sql("PRAGMA table_info(users)")
        columns = [row[1] for row in result]
        if "coffee_count" not in columns:
            await conn.exec_driver_sql(
                "ALTER TABLE users ADD COLUMN coffee_count INTEGER NOT NULL DEFAULT 0"
            )
            await conn.exec_driver_sql(
                "UPDATE users SET coffee_count = 0 WHERE coffee_count IS NULL"
            )

    # Ensure default accounts exist
    async with async_session() as session:
        for username, raw_password in DEFAULT_USERS:
            exists = await session.execute(
                select(User).where(User.username == username)
            )
            if exists.scalar_one_or_none() is not None:
                continue
            session.add(
                User(
                    username=username,
                    password_hash=_hash_password(raw_password),
                    coffee_count=0,
                )
            )
        await session.commit()


async def get_user_by_username(username: str) -> Optional[User]:
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.username == username)
        )
        return result.scalar_one_or_none()


async def create_user(username: str, password: str) -> User:
    async with async_session() as session:
        user = User(
            username=username,
            password_hash=_hash_password(password),
            coffee_count=0,
        )
        session.add(user)
        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()
            raise
        await session.refresh(user)
        return user


async def authenticate_user(username: str, password: str) -> Optional[dict]:
    async with async_session() as session:
        result = await session.execute(select(User).where(User.username == username))
        user = result.scalar_one_or_none()
        if user is None:
            return None
        if _hash_password(password) != user.password_hash:
            return None
        return {"id": user.id, "username": user.username}


async def increment_coffee_count(user_id: int) -> Optional[int]:
    async with async_session() as session:
        user = await session.get(User, user_id)
        if user is None:
            return None
        user.coffee_count = (user.coffee_count or 0) + 1
        await session.commit()
        await session.refresh(user)
        return user.coffee_count
