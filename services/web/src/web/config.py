from zoneinfo import ZoneInfo

from pydantic import AnyHttpUrl, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Настройки из переменных окружения с префиксом WEB_."""

    model_config = SettingsConfigDict(env_prefix="WEB_")

    inventory_url: AnyHttpUrl
    order_url: AnyHttpUrl
    # Ключ подписи cookie с корзиной: без него корзину можно подделать.
    session_secret: SecretStr
    # В БД время в UTC, покупателю показываем по его часовому поясу.
    timezone: str = "Europe/Moscow"

    @property
    def zone(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)
