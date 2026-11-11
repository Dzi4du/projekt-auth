#!/usr/bin/env bash
# Demonstracja na zajęcia: pokazuje hashe w bazie i działanie JWT na /api/me.
# Wymaga: docker compose up -d, curl, jq (opcjonalnie python3 zamiast jq).
set -euo pipefail
API=http://localhost:8000
EMAIL="demo_$RANDOM@example.com"
PASS="SuperTajne!2026"

step() { printf '\n\033[1;34m== %s ==\033[0m\n' "$*"; }
json() { python3 -c "import sys,json; print(json.load(sys.stdin)['$1'])"; }

step "1. Rejestracja użytkownika $EMAIL"
curl -s -X POST $API/auth/register -H 'Content-Type: application/json' \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASS\",\"display_name\":\"Demo\"}"; echo

step "2. Co jest w bazie? (hasło jako hash Argon2id, nie jawny tekst)"
docker compose exec -T db psql -U app -d app -c \
  "SELECT id, email, password_hash FROM users WHERE email = '$EMAIL';"

step "3. Chroniony endpoint BEZ tokenu -> oczekiwane 401"
curl -s -o /dev/null -w 'HTTP %{http_code}\n' $API/api/me

step "4. Logowanie -> JWT"
RESP=$(curl -s -X POST $API/auth/login -H 'Content-Type: application/json' \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASS\"}")
TOKEN=$(echo "$RESP" | json access_token)
REFRESH=$(echo "$RESP" | json refresh_token)
echo "access_token: ${TOKEN:0:60}..."
echo "Zawartość (payload) tokenu:"
echo "$TOKEN" | cut -d. -f2 | python3 -c "import sys,base64,json; s=sys.stdin.read().strip(); print(json.dumps(json.loads(base64.urlsafe_b64decode(s+'='*(-len(s)%4))),indent=2))"

step "5. Chroniony endpoint Z tokenem -> oczekiwane 200"
curl -s -w '\nHTTP %{http_code}\n' $API/api/me -H "Authorization: Bearer $TOKEN"

step "6. Podrobiony token (zmieniona sygnatura) -> oczekiwane 401"
curl -s -w '\nHTTP %{http_code}\n' $API/api/me -H "Authorization: Bearer ${TOKEN%.*}.AAAA${TOKEN##*.}"

step "7. Złe hasło -> oczekiwane 401"
curl -s -w '\nHTTP %{http_code}\n' -X POST $API/auth/login -H 'Content-Type: application/json' \
  -d "{\"email\":\"$EMAIL\",\"password\":\"zle\"}"

step "8. Refresh token w bazie też jest tylko skrótem SHA-256"
echo "token od klienta: ${REFRESH}"
docker compose exec -T db psql -U app -d app -c \
  "SELECT token_hash, expires_at, revoked_at FROM refresh_tokens ORDER BY id DESC LIMIT 1;"
