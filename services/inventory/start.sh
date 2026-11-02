#!/bin/sh
# Миграции и наполнение каталога безопасно запускать при каждом старте:
# alembic применяет только новые миграции, сид не трогает существующие записи.
set -eu

alembic upgrade head
python -m inventory.seed
exec uvicorn inventory.api.app:create_app --factory --host 0.0.0.0 --port 8000
