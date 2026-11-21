from __future__ import annotations

import hashlib
import secrets
from typing import Annotated, Optional

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from .database import User, get_session

bearer_scheme = HTTPBearer(auto_error=False)


def hash_access_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def generate_access_token() -> str:
    return secrets.token_urlsafe(32)


def get_current_user(
    credentials: Annotated[Optional[HTTPAuthorizationCredentials], Depends(bearer_scheme)],
    session: Annotated[Session, Depends(get_session)],
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Требуется авторизация")
    user = session.scalar(
        select(User).where(User.token_hash == hash_access_token(credentials.credentials))
    )
    if user is None:
        raise HTTPException(status_code=401, detail="Недействительный токен")
    return user
