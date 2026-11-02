"""Сборка FastAPI-приложения.

Запуск: uvicorn order.api.app:create_app --factory
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from order.api.routes import router
from order.config import Settings
from order.domain.errors import OrderNotFoundError
from order.storage.db import create_engine, create_session_factory


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine = create_engine(str(settings.database_url))
        app.state.session_factory = create_session_factory(engine)
        yield
        await engine.dispose()

    app = FastAPI(title="order", lifespan=lifespan)
    app.include_router(router)

    @app.exception_handler(OrderNotFoundError)
    async def not_found(request: Request, exc: OrderNotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    return app
