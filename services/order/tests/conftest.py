import pytest

from order.service.orders import OrderService

from .fakes import FakeOrderRepository, FakeOutbox


@pytest.fixture
def repository() -> FakeOrderRepository:
    return FakeOrderRepository()


@pytest.fixture
def outbox() -> FakeOutbox:
    return FakeOutbox()


@pytest.fixture
def service(repository: FakeOrderRepository, outbox: FakeOutbox) -> OrderService:
    return OrderService(repository, outbox)
