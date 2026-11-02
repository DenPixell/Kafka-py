from pydantic import PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Настройки из переменных окружения с префиксом INVENTORY_.

    Если переменной нет или она с ошибкой, сервис упадёт при старте с понятным
    сообщением, а не посреди обработки запроса.
    """

    model_config = SettingsConfigDict(env_prefix="INVENTORY_")

    database_url: PostgresDsn
    kafka_bootstrap_servers: str = "localhost:9092"
