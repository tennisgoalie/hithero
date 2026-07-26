"""Compatibility ASGI entry point; application composition lives in backend.main."""

import os

import bleach
from passlib.hash import sha256_crypt
from sqlalchemy import create_engine, func
from sqlalchemy.pool import StaticPool

from backend.core.auth import (
    get_current_email,
    get_current_id,
    get_current_role,
    get_index_cookie,
    set_teacher_session,
)
from backend.core.settings import (
    get_cors_allow_origins,
    session_cookie_https_only,
)
from backend.db.base import Base
from backend.db.models import (
    ForumComment,
    ForumPost,
    NewUsers,
    PasswordResetToken,
    PostVote,
    RegisteredUsers,
    School,
    TeacherList,
)
from backend.db.session import (
    build_database_url,
    build_engine_kwargs,
    ensure_sqlite_database_directory,
)
from backend.main import app, legacy_jobs
from backend.schemas.forum import PostUpdate, VoteInput


APP_ENV = os.getenv("APP_ENV", "").lower()
TEST_RECAPTCHA_TOKEN = os.getenv("TEST_RECAPTCHA_TOKEN", "hithero-test-recaptcha")
ALLOWED_TAGS = ["b", "i", "em", "strong", "a", "p", "br"]
ALLOWED_ATTRS = {"a": ["href"]}
ALLOWED_PROTOCOLS = ["http", "https", "mailto"]
database_resources = app.state.database_resources
SQLALCHEMY_DATABASE_URL = database_resources.database_url
engine = database_resources.engine
SessionLocal = database_resources.session_factory


def init_db():
    Base.metadata.create_all(bind=engine)


def database_random_ordering():
    if SQLALCHEMY_DATABASE_URL.startswith("sqlite"):
        return func.random()
    return func.newid()


__all__ = [
    "app",
    "ALLOWED_ATTRS",
    "ALLOWED_PROTOCOLS",
    "ALLOWED_TAGS",
    "APP_ENV",
    "Base",
    "ForumComment",
    "ForumPost",
    "NewUsers",
    "PasswordResetToken",
    "PostUpdate",
    "PostVote",
    "RegisteredUsers",
    "SQLALCHEMY_DATABASE_URL",
    "School",
    "SessionLocal",
    "StaticPool",
    "TeacherList",
    "TEST_RECAPTCHA_TOKEN",
    "VoteInput",
    "build_database_url",
    "build_engine_kwargs",
    "create_engine",
    "database_random_ordering",
    "ensure_sqlite_database_directory",
    "get_cors_allow_origins",
    "get_current_email",
    "get_current_id",
    "get_current_role",
    "get_index_cookie",
    "legacy_jobs",
    "engine",
    "bleach",
    "init_db",
    "set_teacher_session",
]


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
