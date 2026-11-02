"""Запуск: python -m inventory.seed"""

import asyncio

from inventory.config import Settings
from inventory.seed.catalog import load_catalog, seed_catalog
from inventory.storage.db import create_engine, create_session_factory


async def main() -> None:
    engine = create_engine(str(Settings().database_url))
    session_factory = create_session_factory(engine)
    async with session_factory.begin() as session:
        await seed_catalog(session, load_catalog())
    await engine.dispose()


asyncio.run(main())
