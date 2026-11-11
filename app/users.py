"""Zarządzanie użytkownikami: własne konto (hasło, e-mail, profil) oraz
operacje administratora (lista kont, zmiana roli, usuwanie)."""
from typing import Annotated

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Query, status
from psycopg.rows import dict_row

from . import config
from .auth_jwt import CurrentUser, Db
from .schemas import EmailChangeIn, PasswordChangeIn, ProfileIn, RoleIn, UserOut
from .security import hash_password, verify_password

router = APIRouter(prefix="/api", tags=["Użytkownicy"])

_USER_COLS = "id, email, display_name, role, created_at"


# ---------------------------------------------------------------------------
# Konto administratora tworzone przy starcie (ADMIN_EMAIL / ADMIN_PASSWORD)
# ---------------------------------------------------------------------------
def ensure_admin() -> None:
    if not (config.ADMIN_EMAIL and config.ADMIN_PASSWORD):
        return
    with psycopg.connect(config.DATABASE_URL) as conn:
        # Istniejącemu kontu nadajemy tylko rolę – hasła nie nadpisujemy.
        conn.execute(
            """INSERT INTO users (email, password_hash, display_name, role)
               VALUES (%s, %s, 'Administrator', 'admin')
               ON CONFLICT (email) DO UPDATE SET role = 'admin'""",
            (config.ADMIN_EMAIL, hash_password(config.ADMIN_PASSWORD)),
        )


# ---------------------------------------------------------------------------
# Autoryzacja: rola jest czytana z bazy przy każdym żądaniu (current_user),
# więc odebranie uprawnień działa natychmiast, bez czekania na wygaśnięcie JWT.
# ---------------------------------------------------------------------------
def require_admin(user: CurrentUser) -> dict:
    if user["role"] != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Wymagana rola administratora")
    return user


Admin = Annotated[dict, Depends(require_admin)]


def _check_current_password(db: psycopg.Connection, user_id: int, password: str) -> None:
    row = db.execute("SELECT password_hash FROM users WHERE id = %s", (user_id,)).fetchone()
    if not verify_password(row["password_hash"], password):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Nieprawidłowe obecne hasło")


def _revoke_refresh_tokens(db: psycopg.Connection, user_id: int) -> None:
    db.execute(
        "UPDATE refresh_tokens SET revoked_at = now() WHERE user_id = %s AND revoked_at IS NULL",
        (user_id,),
    )


# ------------------------------ własne konto --------------------------------
@router.patch("/me", response_model=UserOut)
def update_profile(body: ProfileIn, user: CurrentUser, db: Db):
    """Zmiana wyświetlanej nazwy."""
    return db.execute(
        f"UPDATE users SET display_name = %s WHERE id = %s RETURNING {_USER_COLS}",
        (body.display_name, user["id"]),
    ).fetchone()


@router.put("/me/password", status_code=204)
def change_password(body: PasswordChangeIn, user: CurrentUser, db: Db):
    """Zmiana hasła. Wymaga obecnego hasła; wylogowuje wszystkie sesje
    (unieważnia refresh tokeny)."""
    _check_current_password(db, user["id"], body.current_password)
    db.execute("UPDATE users SET password_hash = %s WHERE id = %s",
               (hash_password(body.new_password), user["id"]))
    _revoke_refresh_tokens(db, user["id"])


@router.put("/me/email", response_model=UserOut)
def change_email(body: EmailChangeIn, user: CurrentUser, db: Db):
    """Zmiana adresu e-mail (loginu). Wymaga obecnego hasła."""
    _check_current_password(db, user["id"], body.current_password)
    try:
        return db.execute(
            f"UPDATE users SET email = %s WHERE id = %s RETURNING {_USER_COLS}",
            (body.new_email, user["id"]),
        ).fetchone()
    except psycopg.errors.UniqueViolation as exc:
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "Ten e-mail jest już zajęty") from exc


# ------------------------------ administrator -------------------------------
@router.get("/users", response_model=list[UserOut])
def list_users(
    admin: Admin, db: Db,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    return db.execute(
        f"SELECT {_USER_COLS} FROM users ORDER BY id LIMIT %s OFFSET %s",
        (limit, offset),
    ).fetchall()


@router.get("/users/{user_id}", response_model=UserOut)
def get_user(user_id: int, admin: Admin, db: Db):
    row = db.execute(f"SELECT {_USER_COLS} FROM users WHERE id = %s", (user_id,)).fetchone()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Nie ma takiego użytkownika")
    return row


@router.put("/users/{user_id}/role", response_model=UserOut)
def set_role(user_id: int, body: RoleIn, admin: Admin, db: Db):
    """Nadanie lub odebranie roli administratora."""
    if user_id == admin["id"]:
        # chroni przed sytuacją, w której w systemie nie zostaje żaden admin
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            "Nie można zmienić własnej roli")
    row = db.execute(
        f"UPDATE users SET role = %s WHERE id = %s RETURNING {_USER_COLS}",
        (body.role, user_id),
    ).fetchone()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Nie ma takiego użytkownika")
    return row


@router.delete("/users/{user_id}", status_code=204)
def delete_user(user_id: int, admin: Admin, db: Db):
    """Usuwa konto wraz z jego notatkami i tokenami (ON DELETE CASCADE)."""
    if user_id == admin["id"]:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            "Nie można usunąć własnego konta")
    deleted = db.execute("DELETE FROM users WHERE id = %s RETURNING id", (user_id,)).fetchone()
    if deleted is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Nie ma takiego użytkownika")
