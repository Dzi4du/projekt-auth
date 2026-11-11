"""Zakres na 4.0 – logowanie przez OAuth 2.0 (GitHub, przepływ Authorization Code).

Przebieg:
 1. /oauth/login    -> przekierowanie na github.com z client_id, state i code_challenge (PKCE)
 2. użytkownik loguje się na GitHubie i zgadza się udostępnić dane
 3. /oauth/callback -> GitHub wraca z ?code=...&state=...
    sprawdzamy state (ochrona CSRF), wymieniamy code na access token GitHuba
    (serwer-serwer, z client_secret i code_verifier), pobieramy profil,
    zakładamy/łączymy konto w naszej bazie i zapisujemy user_id w sesji
    (podpisane ciasteczko HttpOnly).
 4. /oauth/me       -> chroniony endpoint; działa tylko po zalogowaniu przez OAuth.
"""
import base64
import hashlib
import secrets
from typing import Annotated
from urllib.parse import urlencode

import httpx
import psycopg
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse

from . import config
from .db import get_db
from .schemas import UserOut

router = APIRouter(prefix="/oauth", tags=["OAuth – GitHub (4.0)"])
Db = Annotated[psycopg.Connection, Depends(get_db)]

AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
TOKEN_URL = "https://github.com/login/oauth/access_token"
API = "https://api.github.com"


def _require_config():
    if not (config.GITHUB_CLIENT_ID and config.GITHUB_CLIENT_SECRET):
        raise HTTPException(500, "Ustaw GITHUB_CLIENT_ID i GITHUB_CLIENT_SECRET w pliku .env")


@router.get("/login")
def oauth_login(request: Request):
    _require_config()
    state = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    request.session["oauth_state"] = state
    request.session["oauth_verifier"] = verifier
    params = {
        "client_id": config.GITHUB_CLIENT_ID,
        "redirect_uri": config.GITHUB_REDIRECT_URI,
        "scope": "read:user user:email",
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    return RedirectResponse(f"{AUTHORIZE_URL}?{urlencode(params)}")


@router.get("/callback")
def oauth_callback(request: Request, db: Db, code: str = "", state: str = ""):
    _require_config()
    expected = request.session.pop("oauth_state", None)
    verifier = request.session.pop("oauth_verifier", None)
    if not code or not expected or not secrets.compare_digest(state, expected):
        raise HTTPException(400, "Nieprawidłowy parametr state (możliwy atak CSRF)")

    with httpx.Client(timeout=10) as client:
        tok = client.post(TOKEN_URL, headers={"Accept": "application/json"}, data={
            "client_id": config.GITHUB_CLIENT_ID,
            "client_secret": config.GITHUB_CLIENT_SECRET,
            "code": code,
            "redirect_uri": config.GITHUB_REDIRECT_URI,
            "code_verifier": verifier,
        }).json()
        if "access_token" not in tok:
            raise HTTPException(400, f"GitHub odrzucił kod: {tok.get('error_description', tok)}")
        gh = {"Authorization": f"Bearer {tok['access_token']}",
              "Accept": "application/vnd.github+json"}
        profile = client.get(f"{API}/user", headers=gh).json()
        email = profile.get("email")
        if not email:  # e-mail może być prywatny – pobieramy listę
            emails = client.get(f"{API}/user/emails", headers=gh).json()
            email = next((e["email"] for e in emails
                          if e.get("primary") and e.get("verified")), None)
    if not email:
        raise HTTPException(400, "Konto GitHub nie ma zweryfikowanego e-maila")

    user_id = _upsert_user(db, str(profile["id"]), email,
                           profile.get("name") or profile.get("login"))
    request.session.clear()
    request.session["user_id"] = user_id
    return RedirectResponse("/oauth/me", status_code=303)


def _upsert_user(db: psycopg.Connection, gh_id: str, email: str, name: str) -> int:
    row = db.execute(
        "SELECT user_id FROM oauth_accounts WHERE provider = 'github' AND provider_user_id = %s",
        (gh_id,),
    ).fetchone()
    if row:
        return row["user_id"]
    user = db.execute("SELECT id FROM users WHERE email = %s", (email,)).fetchone()
    if user is None:  # nowe konto bez hasła – logowanie tylko przez GitHuba
        user = db.execute(
            "INSERT INTO users (email, display_name) VALUES (%s, %s) RETURNING id",
            (email, name),
        ).fetchone()
    db.execute(
        "INSERT INTO oauth_accounts (user_id, provider, provider_user_id) VALUES (%s, 'github', %s)",
        (user["id"], gh_id),
    )
    return user["id"]


def session_user(request: Request, db: Db) -> dict:
    user_id = request.session.get("user_id")
    if user_id is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED,
                            "Niezalogowany – przejdź do /oauth/login")
    user = db.execute(
        "SELECT id, email, display_name, role, created_at FROM users WHERE id = %s", (user_id,)
    ).fetchone()
    if user is None:
        request.session.clear()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sesja nieważna")
    return user


@router.get("/me", response_model=UserOut)
def oauth_me(user: Annotated[dict, Depends(session_user)]):
    """Chroniony endpoint – dostępny tylko po zalogowaniu przez GitHub."""
    return user


@router.get("/logout")
def oauth_logout(request: Request):
    request.session.clear()
    return RedirectResponse("/", status_code=303)
