class OrderNotFoundError(Exception):
    """Заказа нет или он принадлежит другому пользователю. API отвечает 404."""

    def __init__(self, order_id: object) -> None:
        super().__init__(f"Заказ {order_id} не найден")


class InvalidTransitionError(Exception):
    """Переход статуса, которого нет в машине состояний. Это ошибка в коде саги."""
