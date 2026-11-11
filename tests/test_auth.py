"""Testy end-to-end na prawdziwej bazie PostgreSQL.
Uruchomienie:  docker compose exec api pytest -v
"""
import uuid

import jwt
import psycopg
import pytest
from fastapi.testclient import TestClient

from app import config
from app.main import app

client = TestClient(app)


@pytest.fixture
def creds():
    return {"email": f"test_{uuid.uuid4().hex[:8]}@example.com",
            "password": "BardzoTajne!123"}


def _login(creds):
    client.post("/auth/register", json=creds)
    r = client.post("/auth/login", json=creds)
    assert r.status_code == 200
    return r.json()


# ---------------------------- 3.0: hashowanie ------------------------------
def test_haslo_w_bazie_jest_hashem_argon2id(creds):
    assert client.post("/auth/register", json=creds).status_code == 201
    with psycopg.connect(config.DATABASE_URL) as conn:
        (h,) = conn.execute("SELECT password_hash FROM users WHERE email = %s",
                            (creds["email"],)).fetchone()
    assert h.startswith("$argon2id$v=19$m=65536,t=3,p=4$")
    assert creds["password"] not in h


def test_te_same_hasla_daja_rozne_hashe():
    p = "IdentyczneHaslo1"
    for _ in range(2):
        client.post("/auth/register", json={"email": f"s_{uuid.uuid4().hex[:8]}@ex.com", "password": p})
    with psycopg.connect(config.DATABASE_URL) as conn:
        hashes = [r[0] for r in conn.execute(
            "SELECT password_hash FROM users ORDER BY id DESC LIMIT 2")]
    assert hashes[0] != hashes[1]  # różna sól


def test_duplikat_emaila(creds):
    client.post("/auth/register", json=creds)
    assert client.post("/auth/register", json=creds).status_code == 409


# ---------------------------- 5.0: JWT -------------------------------------
def test_zle_haslo(creds):
    client.post("/auth/register", json=creds)
    r = client.post("/auth/login", json={**creds, "password": "zle-haslo"})
    assert r.status_code == 401


def test_chroniony_endpoint_bez_tokenu():
    assert client.get("/api/me").status_code == 401


def test_chroniony_endpoint_z_tokenem(creds):
    tokens = _login(creds)
    r = client.get("/api/me", headers={"Authorization": f"Bearer {tokens['access_token']}"})
    assert r.status_code == 200
    assert r.json()["email"] == creds["email"]


def test_podrobiony_token(creds):
    tokens = _login(creds)
    payload = jwt.decode(tokens["access_token"], options={"verify_signature": False})
    payload["sub"] = "1"  # próba podszycia się pod innego użytkownika
    fake = jwt.encode(payload, "zly-klucz-" + "x" * 32, algorithm="HS256")
    assert client.get("/api/me", headers={"Authorization": f"Bearer {fake}"}).status_code == 401


def test_token_alg_none(creds):
    tokens = _login(creds)
    payload = jwt.decode(tokens["access_token"], options={"verify_signature": False})
    fake = jwt.encode(payload, None, algorithm="none")
    assert client.get("/api/me", headers={"Authorization": f"Bearer {fake}"}).status_code == 401


def test_wygasly_token(creds):
    tokens = _login(creds)
    payload = jwt.decode(tokens["access_token"], options={"verify_signature": False})
    payload["exp"] = payload["iat"] - 1
    expired = jwt.encode(payload, config.JWT_SECRET, algorithm="HS256")
    r = client.get("/api/me", headers={"Authorization": f"Bearer {expired}"})
    assert r.status_code == 401 and "wygasł" in r.json()["detail"]


def test_refresh_rotacja_i_logout(creds):
    tokens = _login(creds)
    r = client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert r.status_code == 200
    # stary refresh token po rotacji jest już nieważny
    assert client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]}).status_code == 401
    new = r.json()["refresh_token"]
    assert client.post("/auth/logout", json={"refresh_token": new}).status_code == 204
    assert client.post("/auth/refresh", json={"refresh_token": new}).status_code == 401


def test_notatki_sa_prywatne(creds):
    a = _login(creds)["access_token"]
    b = _login({"email": f"b_{uuid.uuid4().hex[:8]}@ex.com", "password": "HasloB12345"})["access_token"]
    client.post("/api/notes", json={"content": "sekret A"}, headers={"Authorization": f"Bearer {a}"})
    notes_b = client.get("/api/notes", headers={"Authorization": f"Bearer {b}"}).json()
    assert notes_b == []


# ---------------------- zarządzanie użytkownikami --------------------------
def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _new_creds():
    return {"email": f"u_{uuid.uuid4().hex[:8]}@example.com", "password": "BardzoTajne!123"}


def _admin_token():
    """Rejestruje użytkownika i nadaje mu rolę admina bezpośrednio w bazie."""
    creds = _new_creds()
    token = _login(creds)["access_token"]
    with psycopg.connect(config.DATABASE_URL) as conn:
        conn.execute("UPDATE users SET role = 'admin' WHERE email = %s", (creds["email"],))
    return token


def test_nowy_uzytkownik_ma_role_user(creds):
    token = _login(creds)["access_token"]
    assert client.get("/api/me", headers=_auth(token)).json()["role"] == "user"


def test_zmiana_nazwy(creds):
    token = _login(creds)["access_token"]
    r = client.patch("/api/me", json={"display_name": "Jan Kowalski"}, headers=_auth(token))
    assert r.status_code == 200 and r.json()["display_name"] == "Jan Kowalski"


def test_zmiana_hasla(creds):
    tokens = _login(creds)
    new = "NoweLepszeHaslo!456"
    r = client.put("/api/me/password", headers=_auth(tokens["access_token"]),
                   json={"current_password": creds["password"], "new_password": new})
    assert r.status_code == 204
    assert client.post("/auth/login", json=creds).status_code == 401           # stare hasło
    assert client.post("/auth/login", json={**creds, "password": new}).status_code == 200
    # zmiana hasła unieważnia wcześniejsze refresh tokeny
    assert client.post("/auth/refresh",
                       json={"refresh_token": tokens["refresh_token"]}).status_code == 401


def test_zmiana_hasla_wymaga_obecnego_hasla(creds):
    token = _login(creds)["access_token"]
    r = client.put("/api/me/password", headers=_auth(token),
                   json={"current_password": "zle-haslo", "new_password": "NoweLepszeHaslo!456"})
    assert r.status_code == 403
    assert client.post("/auth/login", json=creds).status_code == 200  # hasło bez zmian


def test_zmiana_emaila(creds):
    token = _login(creds)["access_token"]
    new_email = _new_creds()["email"]
    r = client.put("/api/me/email", headers=_auth(token),
                   json={"new_email": new_email, "current_password": creds["password"]})
    assert r.status_code == 200 and r.json()["email"] == new_email
    assert client.post("/auth/login", json=creds).status_code == 401
    assert client.post("/auth/login", json={**creds, "email": new_email}).status_code == 200


def test_zmiana_emaila_na_zajety(creds):
    token = _login(creds)["access_token"]
    other = _new_creds()
    client.post("/auth/register", json=other)
    r = client.put("/api/me/email", headers=_auth(token),
                   json={"new_email": other["email"], "current_password": creds["password"]})
    assert r.status_code == 409


def test_zwykly_uzytkownik_nie_ma_dostepu_do_panelu_admina(creds):
    token = _login(creds)["access_token"]
    assert client.get("/api/users", headers=_auth(token)).status_code == 403
    assert client.put("/api/users/1/role", json={"role": "admin"},
                      headers=_auth(token)).status_code == 403
    assert client.delete("/api/users/1", headers=_auth(token)).status_code == 403
    assert client.get("/api/users").status_code == 401  # bez tokenu


def test_admin_lista_i_zmiana_roli(creds):
    admin = _admin_token()
    user_token = _login(creds)["access_token"]
    user_id = client.get("/api/me", headers=_auth(user_token)).json()["id"]

    assert client.get("/api/users?limit=5", headers=_auth(admin)).status_code == 200
    assert client.get(f"/api/users/{user_id}", headers=_auth(admin)).json()["email"] == creds["email"]

    r = client.put(f"/api/users/{user_id}/role", json={"role": "admin"}, headers=_auth(admin))
    assert r.status_code == 200 and r.json()["role"] == "admin"
    # nowa rola działa od razu, na tym samym tokenie
    assert client.get("/api/users?limit=1", headers=_auth(user_token)).status_code == 200

    client.put(f"/api/users/{user_id}/role", json={"role": "user"}, headers=_auth(admin))
    assert client.get("/api/users?limit=1", headers=_auth(user_token)).status_code == 403
    assert client.put(f"/api/users/{user_id}/role", json={"role": "szef"},
                      headers=_auth(admin)).status_code == 422  # nieznana rola


def test_admin_usuwa_uzytkownika(creds):
    admin = _admin_token()
    user_token = _login(creds)["access_token"]
    user_id = client.get("/api/me", headers=_auth(user_token)).json()["id"]

    assert client.delete(f"/api/users/{user_id}", headers=_auth(admin)).status_code == 204
    assert client.get(f"/api/users/{user_id}", headers=_auth(admin)).status_code == 404
    assert client.get("/api/me", headers=_auth(user_token)).status_code == 401  # konta już nie ma
    assert client.delete(f"/api/users/{user_id}", headers=_auth(admin)).status_code == 404


def test_admin_nie_moze_zablokowac_samego_siebie():
    admin = _admin_token()
    my_id = client.get("/api/me", headers=_auth(admin)).json()["id"]
    assert client.put(f"/api/users/{my_id}/role", json={"role": "user"},
                      headers=_auth(admin)).status_code == 400
    assert client.delete(f"/api/users/{my_id}", headers=_auth(admin)).status_code == 400


# ---------------------------- 4.0: OAuth -----------------------------------
def test_oauth_me_bez_logowania():
    assert TestClient(app).get("/oauth/me").status_code == 401


def test_oauth_callback_odrzuca_zly_state():
    r = TestClient(app).get("/oauth/callback?code=abc&state=podrobiony")
    assert r.status_code in (400, 500)  # 500 gdy brak konfiguracji GitHuba
