"""Сборка витрины.

Запуск: uvicorn web.app:create_app --factory
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException
from starlette.middleware.sessions import SessionMiddleware

from web import formatting
from web.clients.catalog import CatalogClient
from web.clients.errors import ServiceUnavailableError
from web.clients.orders import OrderClient
from web.config import Settings
from web.routes import render, router

HERE = Path(__file__).parent


def create_templates(settings: Settings) -> Jinja2Templates:
    templates = Jinja2Templates(directory=HERE / "templates")
    templates.env.filters.update(
        money=formatting.money,
        storage=formatting.storage,
        screen=formatting.screen,
        status_label=formatting.status_label,
        status_tone=formatting.status_tone,
        cancel_reason=formatting.cancel_reason,
        country=formatting.country,
        local_time=lambda moment, pattern="%d.%m.%Y %H:%M": formatting.local_time(
            moment, settings.zone, pattern
        ),
    )
    return templates


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        timeout = httpx.Timeout(5.0)
        async with (
            httpx.AsyncClient(base_url=str(settings.inventory_url), timeout=timeout) as inventory,
            httpx.AsyncClient(base_url=str(settings.order_url), timeout=timeout) as order,
        ):
            app.state.catalog = CatalogClient(inventory)
            app.state.orders = OrderClient(order)
            yield

    app = FastAPI(title="web", lifespan=lifespan, docs_url=None, redoc_url=None)
    app.state.templates = create_templates(settings)
    # SameSite=Lax: браузер не отправит cookie с POST-запросом с чужого сайта,
    # поэтому чужая страница не сможет оформить заказ от имени покупателя.
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.session_secret.get_secret_value(),
        same_site="lax",
        session_cookie="cart",
    )
    app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")
    app.include_router(router)

    @app.exception_handler(ServiceUnavailableError)
    async def unavailable(request: Request, exc: ServiceUnavailableError) -> Response:
        return render(
            request,
            "error.html",
            status_code=503,
            title="Сервис временно недоступен",
            message="Попробуйте обновить страницу через минуту.",
        )

    @app.exception_handler(HTTPException)
    async def not_found(request: Request, exc: HTTPException) -> Response:
        return render(
            request,
            "error.html",
            status_code=exc.status_code,
            title="Страница не найдена",
            message="Возможно, ссылка устарела.",
        )

    return app
