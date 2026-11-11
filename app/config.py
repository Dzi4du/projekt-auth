"""Konfiguracja z zmiennych środowiskowych (plik .env ładuje docker compose)."""
import os


def _required(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Brak wymaganej zmiennej środowiskowej: {name}")
    return value


DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://app:app@localhost:5432/app"
)

# --- JWT (5.0) ---
JWT_SECRET = _required("JWT_SECRET")          # min. 32 losowe bajty
JWT_ALGORITHM = "HS256"
JWT_ISSUER = os.environ.get("JWT_ISSUER", "projekt-auth")
JWT_AUDIENCE = os.environ.get("JWT_AUDIENCE", "projekt-auth-api")
ACCESS_TOKEN_MINUTES = int(os.environ.get("ACCESS_TOKEN_MINUTES", "15"))
REFRESH_TOKEN_DAYS = int(os.environ.get("REFRESH_TOKEN_DAYS", "7"))

if len(JWT_SECRET) < 32:
    raise RuntimeError("JWT_SECRET musi mieć co najmniej 32 znaki")

# --- Konto administratora (opcjonalne) ---
# Jeśli oba ustawione, przy starcie aplikacji powstaje konto z rolą 'admin'.
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")

# --- OAuth / GitHub (4.0) ---
SESSION_SECRET = _required("SESSION_SECRET")
GITHUB_CLIENT_ID = os.environ.get("GITHUB_CLIENT_ID", "")
GITHUB_CLIENT_SECRET = os.environ.get("GITHUB_CLIENT_SECRET", "")
GITHUB_REDIRECT_URI = os.environ.get(
    "GITHUB_REDIRECT_URI", "http://localhost:8000/oauth/callback"
)
