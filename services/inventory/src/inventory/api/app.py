"""Сборка FastAPI-приложения.

Запуск: uvicorn inventory.api.app:create_app --factory
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from inventory.api.routes import router
from inventory.config import Settings
from inventory.domain.errors import NotFoundError
from inventory.storage.db import create_engine, create_session_factory


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine = create_engine(str(settings.database_url))
        app.state.session_factory = create_session_factory(engine)
        yield
        await engine.dispose()

    app = FastAPI(title="inventory", lifespan=lifespan)
    app.include_router(router)

    # Доменные ошибки переводятся в HTTP-коды в одном месте, а не в каждом обработчике.
    @app.exception_handler(NotFoundError)
    async def not_found(request: Request, exc: NotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    return app
