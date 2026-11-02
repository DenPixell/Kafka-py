from collections.abc import AsyncIterator
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, status

from order.api.schemas import CreateOrderIn, OrderOut
from order.service.orders import OrderService
from order.storage.order_repository import PostgresOrderRepository
from order.storage.tables import outbox
from outbox import OutboxWriter

router = APIRouter()


async def get_order_service(request: Request) -> AsyncIterator[OrderService]:
    """Одна транзакция на запрос: заказ и сообщение в outbox коммитятся вместе."""
    async with request.app.state.session_factory.begin() as session:
        yield OrderService(PostgresOrderRepository(session), OutboxWriter(session, outbox))


Orders = Annotated[OrderService, Depends(get_order_service)]
# Имитация API Gateway: он проверил токен и передал id пользователя заголовком.
UserId = Annotated[str, Header(alias="X-User-Id", min_length=1, max_length=64)]


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/orders", status_code=status.HTTP_202_ACCEPTED)
async def create_order(body: CreateOrderIn, user_id: UserId, orders: Orders) -> OrderOut:
    """202, а не 201: заказ принят, но ещё проходит резерв и проверку."""
    order = await orders.place_order(
        user_id=user_id,
        delivery_country=body.delivery_country,
        items=[item.to_domain() for item in body.items],
    )
    return OrderOut.from_domain(order)


@router.get("/orders/{order_id}")
async def get_order(order_id: UUID, user_id: UserId, orders: Orders) -> OrderOut:
    return OrderOut.from_domain(await orders.get_order(order_id, user_id))
