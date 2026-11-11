-- Schemat bazy danych (PostgreSQL). Wykonywany automatycznie przy pierwszym
-- starcie kontenera (docker-entrypoint-initdb.d).

CREATE EXTENSION IF NOT EXISTS citext;

-- Użytkownicy. Hasło NIGDY nie jest przechowywane jawnie – tylko hash Argon2id
-- w formacie PHC: $argon2id$v=19$m=65536,t=3,p=4$<sól>$<hash>
-- (sól jest losowa dla każdego hasła i zapisana w tym samym napisie).
-- password_hash może być NULL dla kont założonych wyłącznie przez OAuth (GitHub).
CREATE TABLE users (
    id            BIGSERIAL PRIMARY KEY,
    email         CITEXT      NOT NULL UNIQUE,
    password_hash TEXT,
    display_name  TEXT,
    -- Rola decyduje o uprawnieniach: 'admin' może zarządzać innymi kontami.
    role          TEXT        NOT NULL DEFAULT 'user',
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT password_hash_is_argon2id
        CHECK (password_hash IS NULL OR password_hash LIKE '$argon2id$%'),
    CONSTRAINT role_is_known CHECK (role IN ('user', 'admin'))
);

-- Powiązania kont z zewnętrznymi dostawcami OAuth (zakres na 4.0).
-- Tokenu dostępu GitHuba nie zapisujemy – jest potrzebny tylko w trakcie logowania.
CREATE TABLE oauth_accounts (
    id               BIGSERIAL PRIMARY KEY,
    user_id          BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    provider         TEXT   NOT NULL,
    provider_user_id TEXT   NOT NULL,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (provider, provider_user_id)
);

-- Refresh tokeny JWT (zakres na 5.0). Też są wartością wrażliwą, więc w bazie
-- trzymamy tylko ich skrót SHA-256 (token ma 256 bitów losowości, więc szybki
-- skrót wystarcza – w odróżnieniu od haseł, które mają małą entropię).
CREATE TABLE refresh_tokens (
    id          BIGSERIAL PRIMARY KEY,
    user_id     BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash  CHAR(64)    NOT NULL UNIQUE,
    expires_at  TIMESTAMPTZ NOT NULL,
    revoked_at  TIMESTAMPTZ,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX refresh_tokens_user_idx ON refresh_tokens(user_id);

-- Przykładowe dane chronione – notatki widoczne tylko dla właściciela.
CREATE TABLE notes (
    id         BIGSERIAL PRIMARY KEY,
    user_id    BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    content    TEXT   NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX notes_user_idx ON notes(user_id);
