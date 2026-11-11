# Projekt: bezpieczne przechowywanie haseł, OAuth i JWT

**Technologie:** Python 3.12 · FastAPI · PostgreSQL 16 · Argon2id (`argon2-cffi`) · PyJWT · OAuth 2.0 (GitHub) · Docker Compose

| Ocena | Wymaganie | Gdzie w projekcie |
|---|---|---|
| **3.0** | Lokalna baza danych, hasła hashowane niezłamanym algorytmem | PostgreSQL w Dockerze (`db/init.sql`), **Argon2id** (`app/security.py`) |
| **4.0** | Logowanie przez OAuth + działający chroniony endpoint | GitHub OAuth 2.0 (`app/auth_oauth.py`), endpoint **`GET /oauth/me`** |
| **5.0** | To samo, ale z JWT zamiast OAuth | Logowanie JWT (`app/auth_jwt.py`), endpointy **`GET /api/me`**, **`GET/POST /api/notes`** |

**Use case:** zarządzanie użytkownikami w szerszej aplikacji – rejestracja, logowanie, role (`user` / `admin`), zmiana hasła, zmiana e-maila, panel administratora. Aplikacja to samo API (bez frontendu) łączące się z bazą PostgreSQL; szczegóły w sekcji [Zarządzanie użytkownikami](#zarządzanie-użytkownikami-baza-danych--service-api).

```
projekt-auth/
├── docker-compose.yml   # PostgreSQL + API
├── Dockerfile
├── .env.example         # wzór konfiguracji (sekrety)
├── db/init.sql          # schemat bazy
├── app/
│   ├── main.py          # aplikacja + chronione endpointy JWT
│   ├── security.py      # Argon2id + tworzenie/weryfikacja JWT
│   ├── auth_jwt.py      # /auth/register, /auth/login, /auth/refresh, /auth/logout
│   ├── auth_oauth.py    # /oauth/login, /oauth/callback, /oauth/me
│   ├── users.py         # zarządzanie kontami: hasło, e-mail, role, panel admina
│   ├── db.py, config.py, schemas.py
├── frontend/            # aplikacja Angular + nginx (osobny kontener)
├── tests/test_auth.py   # testy end-to-end na prawdziwej bazie
└── demo.sh              # skrypt do pokazania na zajęciach
```

---

## Uruchomienie

Wymagany jest tylko **Docker Desktop** (lub Docker + Compose).

```bash
cp .env.example .env
# wygeneruj sekrety i wklej je do .env jako JWT_SECRET i SESSION_SECRET:
python -c "import secrets; print(secrets.token_urlsafe(48))"

docker compose up --build -d
```

- Frontend (Angular): http://localhost:4200
- API: http://localhost:8000
- Swagger UI (interaktywna dokumentacja): http://localhost:8000/docs
- Baza: `localhost:5432`, użytkownik `app`, baza `app`

Testy automatyczne (23 testy, na prawdziwym PostgreSQL):

```bash
docker compose exec api pytest -v
```

Reset bazy (usunięcie danych): `docker compose down -v`

---

## Zarządzanie użytkownikami (baza danych + Service API)

### Baza danych
PostgreSQL 16 w kontenerze, schemat w `db/init.sql`:

| Tabela | Zawartość |
|---|---|
| `users` | konto: e-mail (unikalny, `CITEXT`), hash hasła, nazwa, **rola** (`user` / `admin`, pilnowana przez `CHECK`) |
| `refresh_tokens` | sesje użytkownika (skróty refresh tokenów) |
| `oauth_accounts` | powiązania kont z GitHubem |
| `notes` | przykładowe dane należące do użytkownika |

Tabele podrzędne mają `ON DELETE CASCADE`, więc usunięcie konta usuwa też jego tokeny i notatki.

### Konfiguracja połączenia
Serwis łączy się z bazą adresem ze zmiennej środowiskowej `DATABASE_URL` (`app/config.py`). Ustawia ją `docker-compose.yml`: `postgresql://app:<hasło>@db:5432/app`, gdzie `db` to nazwa kontenera z bazą w sieci Dockera. API startuje dopiero, gdy baza przejdzie healthcheck (`depends_on: condition: service_healthy`). Każde żądanie HTTP dostaje własne połączenie i transakcję (`app/db.py`): sukces = `COMMIT`, wyjątek = `ROLLBACK`.

### Endpointy

| Metoda | Endpoint | Kto | Opis |
|---|---|---|---|
| PATCH | `/api/me` | zalogowany | zmiana wyświetlanej nazwy |
| PUT | `/api/me/password` | zalogowany | zmiana hasła (wymaga obecnego hasła, unieważnia refresh tokeny) |
| PUT | `/api/me/email` | zalogowany | zmiana e-maila (wymaga obecnego hasła; zajęty adres → 409) |
| GET | `/api/users` | admin | lista użytkowników (`limit`, `offset`) |
| GET | `/api/users/{id}` | admin | dane jednego użytkownika |
| PUT | `/api/users/{id}/role` | admin | nadanie / odebranie roli administratora |
| DELETE | `/api/users/{id}` | admin | usunięcie konta |

Zwykły użytkownik dostaje na endpointach administratora **403**, a żądanie bez tokenu – **401**. Rola jest czytana z bazy przy każdym żądaniu, więc odebranie uprawnień działa natychmiast. Administrator nie może zmienić własnej roli ani usunąć własnego konta (żeby system nie został bez admina).

### Konto administratora
Jeśli w `.env` ustawione są `ADMIN_EMAIL` i `ADMIN_PASSWORD`, przy starcie API powstaje konto z rolą `admin` (hasło oczywiście jako hash Argon2id). Kolejnych administratorów nadaje się przez `PUT /api/users/{id}/role`.

### Demonstracja (Swagger UI)
1. `POST /auth/login` danymi admina z `.env` → **Authorize** → wklej `access_token`.
2. `GET /api/users` → lista kont z rolami.
3. Zarejestruj zwykłego użytkownika (`POST /auth/register`), zaloguj się nim i wywołaj `GET /api/users` → **403**.
4. Jako ten użytkownik: `PUT /api/me/password`, potem logowanie starym hasłem → **401**, nowym → **200**.
5. Jako admin: `PUT /api/users/{id}/role` z `{"role": "admin"}` albo `DELETE /api/users/{id}`.
6. Podgląd w bazie: `docker compose exec db psql -U app -d app -c "SELECT id, email, role FROM users;"`

---

## Frontend (Angular)

Dodatkowy, opcjonalny komponent – API działa bez niego. Aplikacja Angular 22 (`frontend/`) jest budowana w Dockerze i serwowana przez nginx pod http://localhost:4200. Node.js nie musi być zainstalowany na komputerze.

| Ekran | Ścieżka | Co robi |
|---|---|---|
| Logowanie / rejestracja | `/login` | `POST /auth/register`, `POST /auth/login` |
| Moje konto | `/account` | dane konta, zmiana nazwy, e-maila i hasła |
| Notatki | `/notes` | lista i dodawanie prywatnych notatek |
| Użytkownicy | `/admin` | tylko dla roli `admin`: lista kont, nadawanie roli, usuwanie |

Jak to działa:
- **Jeden adres, brak CORS** – nginx (`frontend/nginx.conf`) serwuje pliki Angulara, a żądania `/api/...` i `/auth/...` przekazuje do kontenera `api`.
- **JWT** – `auth.interceptor.ts` dokleja nagłówek `Authorization: Bearer ...` do każdego żądania. Gdy access token wygaśnie (401), interceptor sam wymienia refresh token na nową parę i ponawia żądanie; jeśli się nie uda, wylogowuje.
- **Tokeny w `sessionStorage`** – sesja przeżywa odświeżenie strony i znika po zamknięciu karty.
- **Strażnicy tras** (`guards.ts`) tylko ukrywają ekrany; prawdziwa kontrola dostępu jest w API (401 / 403).
- Logowanie przez GitHub (OAuth) pozostaje po stronie API: http://localhost:8000.

---

## 3.0 – baza danych i hashowanie haseł

**Baza:** PostgreSQL 16, uruchamiany lokalnie w kontenerze. Tabele: `users`, `oauth_accounts`, `refresh_tokens`, `notes`.

**Algorytm: Argon2id** – zwycięzca Password Hashing Competition (2015), opisany w standardzie **RFC 9106** i rekomendowany jako pierwszy wybór przez **OWASP Password Storage Cheat Sheet**. Nie jest znany żaden praktyczny atak na Argon2id.

Parametry (profil z RFC 9106): `m = 64 MiB pamięci, t = 3 iteracje, p = 4 wątki`, losowa sól 16 B, wynik 32 B.

Dlaczego to bezpieczne:
- **Sól** – losowa dla każdego hasła, więc te same hasła mają różne hashe, a tęczowe tablice są bezużyteczne.
- **Memory-hard** – każda próba odgadnięcia wymaga 64 MiB RAM, co drastycznie spowalnia łamanie na kartach graficznych i układach ASIC.
- **Celowo wolny** – ~50–100 ms na sprawdzenie; dla użytkownika niezauważalne, dla atakującego miliardy prób stają się niewykonalne.

Dlaczego nie MD5 / SHA-1 / SHA-256: MD5 i SHA-1 mają znane kolizje, a wszystkie trzy są **szybkie** – GPU liczy ich miliardy na sekundę, więc nawet bez kolizji słabe hasła padają atakiem słownikowym.

Jak wygląda hash w bazie:

```bash
docker compose exec db psql -U app -d app -c "SELECT email, password_hash FROM users;"
```
```
$argon2id$v=19$m=65536,t=3,p=4$<sól base64>$<hash base64>
 algorytm  wersja   parametry         sól          wynik
```

Dodatkowe zabezpieczenia:
- `CHECK` w bazie odrzuca każde hasło, które nie jest hashem Argon2id (nie da się przypadkiem zapisać jawnego hasła).
- **Refresh tokeny** też są wartościami wrażliwymi, więc w bazie trzymamy tylko ich skrót SHA-256. (Tu szybki skrót wystarcza, bo token ma 256 bitów losowości – nie da się go zgadnąć słownikiem, w przeciwieństwie do hasła.)
- Przy logowaniu nieistniejącego użytkownika i tak liczony jest Argon2 na hashu-atrapie, żeby czas odpowiedzi nie zdradzał, czy e-mail jest w bazie.
- Gdy parametry Argon2 zostaną kiedyś podniesione, stare hashe są automatycznie przeliczane przy logowaniu (`check_needs_rehash`).
- Wszystkie zapytania SQL są parametryzowane (ochrona przed SQL injection).

---

## 4.0 – logowanie przez OAuth 2.0 (GitHub)

### Konfiguracja (jednorazowo, ok. 2 minuty)
1. Wejdź na https://github.com/settings/developers → **OAuth Apps** → **New OAuth App**.
2. Wypełnij:
   - *Homepage URL:* `http://localhost:8000`
   - *Authorization callback URL:* `http://localhost:8000/oauth/callback`
3. Skopiuj **Client ID**, wygeneruj **Client secret** i wpisz oba do `.env` (`GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET`).
4. `docker compose up -d --force-recreate api`

### Demonstracja
1. Wejdź na http://localhost:8000/oauth/me → **401 Niezalogowany**.
2. Wejdź na http://localhost:8000 → **Zaloguj przez GitHub** → zatwierdź na GitHubie.
3. Nastąpi powrót na `/oauth/me` → **200** z danymi użytkownika z bazy.
4. W bazie: `SELECT * FROM oauth_accounts;` – konto powiązane z ID GitHuba (bez hasła).

### Przepływ (Authorization Code + PKCE)
```
Przeglądarka        Nasza aplikacja                 GitHub
    |  GET /oauth/login  |                              |
    |------------------->| generuje state + PKCE        |
    |<-- 302 redirect ---|----------------------------->|
    |            logowanie i zgoda użytkownika          |
    |<-------------- 302 /oauth/callback?code&state ----|
    |------------------->| sprawdza state (CSRF)        |
    |                    | code + client_secret ------->|
    |                    |<------- access token ---------|
    |                    | GET /user, /user/emails ---->|
    |                    | zapis/połączenie konta w DB  |
    |<-- ciasteczko sesji (HttpOnly, podpisane) --------|
    |  GET /oauth/me  -> 200                            |
```
- **state** – losowa wartość chroniąca przed CSRF (atakujący nie podrzuci ofierze własnego `code`).
- **PKCE** (`code_challenge` / `code_verifier`) – nawet przechwycony `code` jest bezużyteczny bez weryfikatora.
- Token dostępu GitHuba nie jest nigdzie zapisywany – służy tylko do pobrania profilu.

---

## 5.0 – logowanie JWT

| Metoda | Endpoint | Opis |
|---|---|---|
| POST | `/auth/register` | rejestracja (hasło → Argon2id) |
| POST | `/auth/login` | logowanie → `access_token` (JWT, 15 min) + `refresh_token` (7 dni) |
| POST | `/auth/refresh` | nowa para tokenów; stary refresh token zostaje unieważniony (rotacja) |
| POST | `/auth/logout` | unieważnia refresh token |
| GET | `/api/me` | 🔒 dane zalogowanego użytkownika |
| GET / POST | `/api/notes` | 🔒 prywatne notatki użytkownika |

### Demonstracja – opcja A: skrypt
```bash
./demo.sh
```
Pokazuje kolejno: rejestrację, hash w bazie, `401` bez tokenu, logowanie, zawartość JWT, `200` z tokenem, `401` dla podrobionego tokenu i złego hasła, skrót refresh tokenu w bazie.

### Demonstracja – opcja B: Swagger UI (http://localhost:8000/docs)
1. `POST /auth/register` → *Try it out* → podaj e-mail i hasło.
2. `GET /api/me` → *Execute* → **401**.
3. `POST /auth/login` → skopiuj `access_token`.
4. Kliknij **Authorize** (kłódka u góry) → wklej token.
5. `GET /api/me` → **200**. Można też dodać notatkę `POST /api/notes`.
6. Wklej token na https://jwt.io, żeby pokazać jego zawartość, a następnie zmień jeden znak – serwer zwróci 401.

### Demonstracja – opcja C: curl
```bash
curl -X POST localhost:8000/auth/register -H 'Content-Type: application/json' \
     -d '{"email":"jan@example.com","password":"TajneHaslo123"}'
curl -X POST localhost:8000/auth/login -H 'Content-Type: application/json' \
     -d '{"email":"jan@example.com","password":"TajneHaslo123"}'
curl localhost:8000/api/me -H "Authorization: Bearer <access_token>"
```

### Budowa tokenu
```
eyJhbGciOiJIUzI1NiIs...  .  eyJzdWIiOiIxIiwiZW1h...  .  SflKxwRJSMeKKF2QT4fw...
       nagłówek                       payload                    podpis HMAC-SHA256
```
Payload:
```json
{ "sub": "1", "email": "jan@example.com", "type": "access",
  "iss": "projekt-auth", "aud": "projekt-auth-api",
  "iat": 1762880000, "nbf": 1762880000, "exp": 1762880900, "jti": "…uuid…" }
```

### Zabezpieczenia JWT
- Podpis **HS256** z sekretem ≥ 32 znaki przechowywanym w zmiennej środowiskowej (nie w kodzie).
- Serwer akceptuje **wyłącznie** HS256 → ataki `alg: none` i podmiany algorytmu są odrzucane.
- Wymagane i sprawdzane: `exp` (wygaśnięcie), `iss` (wystawca), `aud` (odbiorca), `type` (refresh tokenu nie da się użyć jako access).
- Krótki czas życia access tokenu (15 min) ogranicza skutki jego kradzieży; refresh tokeny są rotowane i można je unieważnić (wylogowanie).
- W JWT nie ma żadnych tajnych danych – payload jest tylko zakodowany base64, **nie zaszyfrowany**.

---

## OAuth a JWT – pytanie, które może paść na obronie

- **OAuth 2.0** to **protokół delegowania autoryzacji**: użytkownik loguje się u zewnętrznego dostawcy (GitHub), a nasza aplikacja nigdy nie widzi jego hasła. Nie określa formatu tokenu.
- **JWT** to **format tokenu**: podpisany, samowystarczalny dokument JSON. Serwer weryfikuje go samym podpisem, bez zaglądania do bazy sesji (bezstanowość).
- W wersji 4.0 po OAuth stan logowania trzyma **sesja** (podpisane ciasteczko). W wersji 5.0 aplikacja **sama** uwierzytelnia hasłem z bazy i wydaje **JWT**, który klient wysyła w nagłówku `Authorization: Bearer …`.
- (Obie rzeczy da się łączyć – np. OpenID Connect wydaje `id_token` w formacie JWT – ale wymaganie mówi o zastosowaniu JWT *zamiast* OAuth, więc tu są rozdzielone.)

> Uwaga: Swagger nazywa schemat logowania „HTTPBearer”. To tylko sposób przesyłania tokenu w nagłówku – nie ma związku z protokołem OAuth z wersji 4.0.

---

## Możliwe rozszerzenia
- RS256/EdDSA (klucz prywatny podpisuje, publiczny weryfikuje) – gdy tokeny sprawdza wiele usług.
- Limit prób logowania (rate limiting) i blokada konta po wielu nieudanych próbach.
- HTTPS (w produkcji ciasteczko sesji z `https_only=True`).
