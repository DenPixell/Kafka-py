class NotFoundError(Exception):
    """Запрошенного объекта нет. API переводит эту ошибку в 404."""


class CategoryNotFoundError(NotFoundError):
    def __init__(self, slug: str) -> None:
        super().__init__(f"Категория {slug!r} не найдена")


class ProductNotFoundError(NotFoundError):
    def __init__(self, slug: str) -> None:
        super().__init__(f"Модель {slug!r} не найдена")
