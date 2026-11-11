# Etap 1: budowanie aplikacji Angular
FROM node:24-slim AS build
WORKDIR /app
ENV NG_CLI_ANALYTICS=false
COPY package.json package-lock.json ./
# Opcjonalny dodatkowy certyfikat CA (np. antywirus/proxy skanujące HTTPS).
# Bez sekretu "extra_ca" ten krok działa jak zwykłe "npm ci".
RUN --mount=type=secret,id=extra_ca \
    if [ -s /run/secrets/extra_ca ]; then \
        export NODE_EXTRA_CA_CERTS=/run/secrets/extra_ca; \
    fi \
    && npm ci
COPY . .
RUN npx ng build

# Etap 2: nginx serwuje gotowe pliki i przekazuje /api oraz /auth do backendu
FROM nginx:stable-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist/frontend/browser /usr/share/nginx/html
EXPOSE 80
