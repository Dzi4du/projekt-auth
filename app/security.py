"""Hashowanie haseł (Argon2id) oraz tokeny JWT."""
import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from . import config

# ---------------------------------------------------------------------------
# Hasła – Argon2id
# ---------------------------------------------------------------------------
# Argon2 wygrał Password Hashing Competition (2015), jest opisany w RFC 9106
# i jest pierwszym wyborem w OWASP Password Storage Cheat Sheet. Do dziś nie
# jest znany praktyczny atak na Argon2id. Jest "memory-hard": każde
# sprawdzenie hasła wymaga 64 MiB RAM, co bardzo utrudnia łamanie na GPU/ASIC.
# Parametry = profil "low memory" z RFC 9106 (domyślne w argon2-cffi):
#   time_cost=3, memory_cost=64 MiB, parallelism=4, sól 16 B, hash 32 B.
_ph = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=4,
                     hash_len=32, salt_len=16)

# Hash "atrapa" – sprawdzamy go, gdy użytkownik nie istnieje, żeby czas
# odpowiedzi nie zdradzał, czy dany e-mail jest w bazie (timing attack).
_DUMMY_HASH = _ph.hash(secrets.token_urlsafe(16))


def hash_password(password: str) -> str:
    return _ph.hash(password)


def verify_password(password_hash: str | None, password: str) -> bool:
    """Porównanie w stałym czasie (robi to biblioteka argon2)."""
    try:
        _ph.verify(password_hash or _DUMMY_HASH, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False
    return password_hash is not None


def needs_rehash(password_hash: str) -> bool:
    """True, jeśli hash powstał ze słabszymi parametrami niż obecne."""
    return _ph.check_needs_rehash(password_hash)


# ---------------------------------------------------------------------------
# JWT – access token
# ---------------------------------------------------------------------------
class TokenError(Exception):
    pass


def create_access_token(user_id: int, email: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "email": email,
        "type": "access",
        "iss": config.JWT_ISSUER,
        "aud": config.JWT_AUDIENCE,
        "iat": now,
        "nbf": now,
        "exp": now + timedelta(minutes=config.ACCESS_TOKEN_MINUTES),
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, config.JWT_SECRET, algorithm=config.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    try:
        payload = jwt.decode(
            token,
            config.JWT_SECRET,
            # Jawna lista algorytmów – chroni przed atakiem "alg: none"
            # i podmianą algorytmu w nagłówku tokenu.
            algorithms=[config.JWT_ALGORITHM],
            audience=config.JWT_AUDIENCE,
            issuer=config.JWT_ISSUER,
            options={"require": ["exp", "iat", "sub", "iss", "aud"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise TokenError("Token wygasł") from exc
    except jwt.InvalidTokenError as exc:
        raise TokenError("Nieprawidłowy token") from exc
    if payload.get("type") != "access":
        raise TokenError("Zły typ tokenu")
    return payload


# ---------------------------------------------------------------------------
# Refresh token – losowy, nieprzezroczysty; w bazie tylko SHA-256
# ---------------------------------------------------------------------------
def new_refresh_token() -> tuple[str, str, datetime]:
    raw = secrets.token_urlsafe(32)  # 256 bitów losowości
    expires = datetime.now(timezone.utc) + timedelta(days=config.REFRESH_TOKEN_DAYS)
    return raw, hash_refresh_token(raw), expires


def hash_refresh_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()
