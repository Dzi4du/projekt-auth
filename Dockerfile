FROM python:3.12-slim
WORKDIR /srv
# żeby "pytest" (bez "python -m") widział pakiet app
ENV PYTHONPATH=/srv
COPY requirements.txt .
# Opcjonalny dodatkowy certyfikat CA (np. antywirus/proxy skanujące HTTPS).
# Bez sekretu "extra_ca" ten krok działa jak zwykłe "pip install".
RUN --mount=type=secret,id=extra_ca \
    if [ -s /run/secrets/extra_ca ]; then \
        cat "$(python -c 'import pip._vendor.certifi as c; print(c.where())')" \
            /run/secrets/extra_ca > /srv/ca-bundle.pem \
        && export PIP_CERT=/srv/ca-bundle.pem; \
    fi \
    && pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY tests ./tests
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
