from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from starlette.middleware.sessions import SessionMiddleware

from . import config
from .auth_jwt import CurrentUser, Db
from .auth_jwt import router as jwt_router
from .auth_oauth import router as oauth_router
from .schemas import NoteIn, NoteOut, UserOut
from .users import ensure_admin
from .users import router as users_router


@asynccontextmanager
async def lifespan(_: FastAPI):
    ensure_admin()  # konto administratora z ADMIN_EMAIL / ADMIN_PASSWORD
    yield


app = FastAPI(
    lifespan=lifespan,
    title="Projekt: bezpieczne uwierzytelnianie",
    description="PostgreSQL + Argon2id (3.0), OAuth/GitHub (4.0), JWT (5.0). "
                "Kliknij **Authorize** i wklej access_token z /auth/login.",
)
# Sesja (podpisane ciasteczko HttpOnly) – używana tylko przez przepływ OAuth.
app.add_middleware(SessionMiddleware, secret_key=config.SESSION_SECRET,
                   same_site="lax", https_only=False, max_age=3600)

app.include_router(jwt_router)
app.include_router(oauth_router)
app.include_router(users_router)


# --------------------------- chronione endpointy JWT ------------------------
@app.get("/api/me", response_model=UserOut, tags=["Chronione (JWT)"])
def me(user: CurrentUser):
    """Zwraca dane zalogowanego użytkownika. Bez ważnego JWT -> 401."""
    return user


@app.get("/api/notes", response_model=list[NoteOut], tags=["Chronione (JWT)"])
def list_notes(user: CurrentUser, db: Db):
    return db.execute(
        "SELECT id, content, created_at FROM notes WHERE user_id = %s ORDER BY id",
        (user["id"],),
    ).fetchall()


@app.post("/api/notes", response_model=NoteOut, status_code=201, tags=["Chronione (JWT)"])
def add_note(body: NoteIn, user: CurrentUser, db: Db):
    return db.execute(
        "INSERT INTO notes (user_id, content) VALUES (%s, %s) RETURNING id, content, created_at",
        (user["id"], body.content),
    ).fetchone()


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def index():
    return """<!doctype html><meta charset="utf-8"><title>Projekt auth</title>
<style>body{font-family:system-ui;max-width:640px;margin:3rem auto;line-height:1.6}
a.btn{display:inline-block;padding:.6rem 1rem;background:#24292f;color:#fff;
border-radius:6px;text-decoration:none}</style>
<h1>Projekt: uwierzytelnianie</h1>
<h3>4.0 – OAuth</h3>
<p><a class="btn" href="/oauth/login">Zaloguj przez GitHub</a></p>
<p>Po zalogowaniu: <a href="/oauth/me">/oauth/me</a> (chroniony) ·
<a href="/oauth/logout">wyloguj</a></p>
<h3>5.0 – JWT</h3>
<p>Swagger UI: <a href="/docs">/docs</a> – zarejestruj się (/auth/register),
zaloguj (/auth/login), kliknij <b>Authorize</b>, wklej access_token
i wywołaj <code>GET /api/me</code>.</p>"""
