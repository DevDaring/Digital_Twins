"""Password hashing (bcrypt) and stateless JWT sessions."""

from __future__ import annotations

import hashlib
import logging
from datetime import UTC, datetime, timedelta
from functools import lru_cache

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select

from pratifalan.config import get_settings
from pratifalan.db import User, session

_bearer = HTTPBearer(auto_error=False)
log = logging.getLogger("pratifalan.auth")
@lru_cache
def _key() -> bytes:
    """HS256 signing key: SHA-256 of JWT_SECRET (always 32 bytes, as RFC 7518 asks).

    Without JWT_SECRET a random secret is generated at process start (config.py): safe, but every
    restart signs everyone out. Deployments should set JWT_SECRET."""
    s = get_settings()
    if s.jwt_secret_generated:
        log.warning("JWT_SECRET is not set: using a random per-process secret (sessions end on restart).")
    return hashlib.sha256(s.jwt_secret.encode()).digest()


def hash_password(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()


def verify_password(pw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode(), hashed.encode())
    except ValueError:
        return False


def make_token(user: User) -> str:
    s = get_settings()
    payload = {"sub": str(user.id), "usr": user.username,
               "exp": datetime.now(UTC) + timedelta(hours=s.jwt_ttl_hours)}
    return jwt.encode(payload, _key(), algorithm="HS256")


def authenticate(username: str, password: str) -> User | None:
    with session() as s:
        u = s.scalar(select(User).where(User.username == username))
        if u and verify_password(password, u.password_hash):
            return u
    return None


def current_user(creds: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> User:
    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not signed in")
    try:
        data = jwt.decode(creds.credentials, _key(), algorithms=["HS256"])
        uid = int(data["sub"])
    except (jwt.PyJWTError, KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session expired, please sign in again") from exc
    with session() as s:
        u = s.get(User, uid)
        if u is None:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Unknown user")
        return u


def user_json(u: User) -> dict:
    return {"username": u.username, "display_name": u.display_name, "roles": u.roles.split(",")}
