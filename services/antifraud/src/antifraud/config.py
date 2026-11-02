from datetime import timedelta

from pydantic import PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict

from antifraud.domain.rules import FrequentOrders, LargeAmount, NewCountry, Rule

RUB = 100


class Settings(BaseSettings):
    """Настройки из переменных окружения с префиксом ANTIFRAUD_.

    Пороги и баллы правил вынесены в настройки: их меняют без выпуска новой версии.
    """

    model_config = SettingsConfigDict(env_prefix="ANTIFRAUD_")

    database_url: PostgresDsn
    kafka_bootstrap_servers: str = "localhost:9092"

    large_amount_rub: int = 400_000
    large_amount_score: int = 50
    frequent_orders_max: int = 3
    frequent_orders_window_minutes: int = 10
    frequent_orders_score: int = 70
    new_country_amount_rub: int = 150_000
    new_country_score: int = 40
    reject_threshold: int = 70

    def rules(self) -> list[Rule]:
        return [
            LargeAmount(
                threshold_kopecks=self.large_amount_rub * RUB, score=self.large_amount_score
            ),
            FrequentOrders(max_orders=self.frequent_orders_max, score=self.frequent_orders_score),
            NewCountry(
                threshold_kopecks=self.new_country_amount_rub * RUB, score=self.new_country_score
            ),
        ]

    @property
    def frequent_orders_window(self) -> timedelta:
        return timedelta(minutes=self.frequent_orders_window_minutes)
