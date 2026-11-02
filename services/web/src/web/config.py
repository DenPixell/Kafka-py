from pydantic import AnyHttpUrl, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Настройки из переменных окружения с префиксом WEB_."""

    model_config = SettingsConfigDict(env_prefix="WEB_")

    inventory_url: AnyHttpUrl
    order_url: AnyHttpUrl
    # Ключ подписи cookie с корзиной: без него корзину можно подделать.
    session_secret: SecretStr
