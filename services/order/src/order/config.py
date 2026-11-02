from pydantic import PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Настройки из переменных окружения с префиксом ORDER_."""

    model_config = SettingsConfigDict(env_prefix="ORDER_")

    database_url: PostgresDsn
    kafka_bootstrap_servers: str = "localhost:9092"
