FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY auth.py server.py ./

# Utilisateur non-root
RUN useradd --system --uid 10001 mcp
USER mcp

ENV HOST=0.0.0.0 PORT=8000
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s CMD python -c "import urllib.request,os;urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\",\"8000\")}/health')"

# Secrets (JWT_SECRET / JWKS_URL...) injectés à l'exécution, jamais dans l'image.
CMD ["python", "server.py"]
