# Общий образ для сервисов. Какой сервис собрать, задаёт аргумент SERVICE:
#   docker build --build-arg SERVICE=inventory .
FROM python:3.12.15-slim

COPY --from=ghcr.io/astral-sh/uv:0.13.6 /uv /bin/uv

ARG SERVICE
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app
COPY . .
RUN uv sync --frozen --no-dev --package "$SERVICE"

RUN useradd --create-home app
USER app

WORKDIR /app/services/$SERVICE
EXPOSE 8000
CMD ["sh", "start.sh"]
