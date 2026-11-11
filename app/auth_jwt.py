"""Zakres na 5.0 – rejestracja, logowanie i autoryzacja tokenem JWT."""
from typing import Annotated

import psycopg
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import (HTTPAuthorizationCredentials, HTTPBearer,
                              OAuth2PasswordRequestForm)

from . import config
from .db import get_db
from .schemas import LoginIn, RefreshIn, RegisterIn, TokenOut, UserOut
from .security import (TokenError, create_access_token, decode_access_token,
                       hash_password, hash_refresh_token, needs_rehash,
                       new_refresh_token, verify_password)

router = APIRouter(prefix="/auth", tags=["JWT (5.0)"])
Db = Annotated[psycopg.Connection, Depends(get_db)]

_bearer = HTTPBearer(auto_error=False)
_UNAUTHORIZED = {"WWW-Authenticate": "Bearer"}


# ---------------------------------------------------------------------------
# Zależność chroniąca endpointy: wymaga nagłówka  Authorization: Bearer <JWT>
# ---------------------------------------------------------------------------
def current_user(
    db: Db,
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> dict:
    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED,
                            "Brak tokenu (nagłówek Authorization: Bearer ...)",
                            headers=_UNAUTHORIZED)
    try:
        payload = decode_access_token(creds.credentials)
    except TokenError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(exc),
                            headers=_UNAUTHORIZED) from exc
    user = db.execute(
        "SELECT id, email, display_name, role, created_at FROM users WHERE id = %s",
        (int(payload["sub"]),),
    ).fetchone()
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Użytkownik nie istnieje",
                            headers=_UNAUTHORIZED)
    return user


CurrentUser = Annotated[dict, Depends(current_user)]


# ---------------------------------------------------------------------------
def _issue_tokens(db: psycopg.Connection, user_id: int, email: str) -> TokenOut:
    raw, digest, expires = new_refresh_token()
    db.execute(
        "INSERT INTO refresh_tokens (user_id, token_hash, expires_at) VALUES (%s, %s, %s)",
        (user_id, digest, expires),
    )
    return TokenOut(
        access_token=create_access_token(user_id, email),
        refresh_token=raw,
        expires_in=config.ACCESS_TOKEN_MINUTES * 60,
    )


def _authenticate(db: psycopg.Connection, email: str, password: str) -> dict:
    user = db.execute(
        "SELECT id, email, password_hash FROM users WHERE email = %s", (email,)
    ).fetchone()
    # verify_password liczy Argon2 także gdy użytkownika nie ma (stały czas).
    if not verify_password(user["password_hash"] if user else None, password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED,
                            "Nieprawidłowy e-mail lub hasło", headers=_UNAUTHORIZED)
    if needs_rehash(user["password_hash"]):
        db.execute("UPDATE users SET password_hash = %s WHERE id = %s",
                   (hash_password(password), user["id"]))
    return user


@router.post("/register", response_model=UserOut, status_code=201)
def register(body: RegisterIn, db: Db):
    try:
        return db.execute(
            """INSERT INTO users (email, password_hash, display_name)
               VALUES (%s, %s, %s)
               RETURNING id, email, display_name, role, created_at""",
            (body.email, hash_password(body.password), body.display_name),
        ).fetchone()
    except psycopg.errors.UniqueViolation as exc:
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "Użytkownik o tym e-mailu już istnieje") from exc


@router.post("/login", response_model=TokenOut)
def login(body: LoginIn, db: Db):
    """Logowanie JSON-em: zwraca access token (JWT) i refresh token."""
    user = _authenticate(db, body.email, body.password)
    return _issue_tokens(db, user["id"], user["email"])


@router.post("/token", response_model=TokenOut, include_in_schema=False)
def login_form(form: Annotated[OAuth2PasswordRequestForm, Depends()], db: Db):
    """To samo co /login, ale jako formularz (wygodne dla narzędzi)."""
    user = _authenticate(db, form.username, form.password)
    return _issue_tokens(db, user["id"], user["email"])


@router.post("/refresh", response_model=TokenOut)
def refresh(body: RefreshIn, db: Db):
    """Wymienia refresh token na nową parę tokenów (rotacja – stary jest unieważniany)."""
    row = db.execute(
        """UPDATE refresh_tokens SET revoked_at = now()
           WHERE token_hash = %s AND revoked_at IS NULL AND expires_at > now()
           RETURNING user_id""",
        (hash_refresh_token(body.refresh_token),),
    ).fetchone()
    if row is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED,
                            "Refresh token nieważny lub wygasł", headers=_UNAUTHORIZED)
    user = db.execute("SELECT id, email FROM users WHERE id = %s",
                      (row["user_id"],)).fetchone()
    return _issue_tokens(db, user["id"], user["email"])


@router.post("/logout", status_code=204)
def logout(body: RefreshIn, db: Db):
    db.execute(
        "UPDATE refresh_tokens SET revoked_at = now() WHERE token_hash = %s AND revoked_at IS NULL",
        (hash_refresh_token(body.refresh_token),),
    )
