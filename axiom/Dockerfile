# syntax=docker/dockerfile:1

# ---------------------------------------------------------------------------
# Stage 1 — builder: install dependencies into an isolated virtualenv
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS builder

WORKDIR /build

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# ---------------------------------------------------------------------------
# Stage 2 — runtime: minimal image, non-root user, only the built venv + app
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS runtime

RUN groupadd --system axiom && useradd --system --gid axiom --create-home axiom

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    AXIOM_DATA_DIR=/app/data \
    OCIF_ENVIRONMENT=production

COPY --from=builder /opt/venv /opt/venv

WORKDIR /app

COPY . .

RUN mkdir -p /app/data && chown -R axiom:axiom /app

USER axiom

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)" || exit 1

CMD ["uvicorn", "api.gateway:create_gateway_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
