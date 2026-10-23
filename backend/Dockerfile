# syntax=docker/dockerfile:1
FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN --mount=type=secret,id=proxy_ca,target=/run/proxy-ca.pem \
    if [ -f /run/proxy-ca.pem ]; then export PIP_CERT=/run/proxy-ca.pem SSL_CERT_FILE=/run/proxy-ca.pem; fi; \
    pip install --no-cache-dir uv==0.12.23 && UV_CACHE_DIR=/tmp/uv uv sync --frozen --no-dev --no-install-project && rm -rf /tmp/uv
COPY backend ./backend
COPY datasets ./datasets
ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8000
CMD ["uvicorn", "backend.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
