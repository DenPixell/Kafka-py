import asyncio

from alembic import context
from sqlalchemy.engine import Connection

from inventory.config import Settings
from inventory.storage.db import create_engine
from inventory.storage.tables import metadata


def run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    # Если адрес передан явно (например, из тестов), берём его, иначе — из окружения.
    url = context.config.get_main_option("sqlalchemy.url") or str(Settings().database_url)
    engine = create_engine(url)
    async with engine.connect() as connection:
        await connection.run_sync(run_migrations)
    await engine.dispose()


asyncio.run(run_async_migrations())
