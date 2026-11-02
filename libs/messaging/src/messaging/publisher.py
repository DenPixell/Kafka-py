from typing import Protocol

from aiokafka import AIOKafkaProducer


class Publisher(Protocol):
    async def publish(self, topic: str, key: str, value: bytes) -> None: ...


class KafkaPublisher:
    """Отправка в Kafka с подтверждением от всех реплик.

    enable_idempotence: если продюсер повторит отправку после сетевой ошибки,
    брокер не запишет сообщение дважды.
    """

    def __init__(self, bootstrap_servers: str) -> None:
        self._producer = AIOKafkaProducer(
            bootstrap_servers=bootstrap_servers,
            acks="all",
            enable_idempotence=True,
        )

    async def start(self) -> None:
        await self._producer.start()

    async def stop(self) -> None:
        await self._producer.stop()

    async def publish(self, topic: str, key: str, value: bytes) -> None:
        await self._producer.send_and_wait(topic, value=value, key=key.encode())
