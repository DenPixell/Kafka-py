# Собирается из корня репозитория: docker build -f services/inventory/Dockerfile .
FROM python:3.12.15-slim

COPY --from=ghcr.io/astral-sh/uv:0.13.6 /uv /bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app
COPY . .
RUN uv sync --frozen --no-dev --package inventory

RUN useradd --create-home app
USER app

WORKDIR /app/services/inventory
EXPOSE 8000
CMD ["sh", "start.sh"]
