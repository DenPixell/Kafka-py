import asyncio
import os
import signal

import pytest

from messaging import run_until_stopped


async def test_sigterm_cancels_jobs_and_lets_them_clean_up() -> None:
    cleaned_up: list[str] = []

    async def job(name: str) -> None:
        try:
            await asyncio.Event().wait()
        finally:
            cleaned_up.append(name)

    async def send_sigterm() -> None:
        await asyncio.sleep(0.05)
        os.kill(os.getpid(), signal.SIGTERM)

    sender = asyncio.create_task(send_sigterm())
    await run_until_stopped(job("consumer"), job("relay"))
    await sender

    assert sorted(cleaned_up) == ["consumer", "relay"]


async def test_failed_job_stops_the_rest_and_is_reported() -> None:
    cleaned_up: list[str] = []

    async def failing() -> None:
        raise RuntimeError("Kafka недоступна")

    async def waiting() -> None:
        try:
            await asyncio.Event().wait()
        finally:
            cleaned_up.append("waiting")

    with pytest.raises(RuntimeError, match="Kafka недоступна"):
        await run_until_stopped(failing(), waiting())

    assert cleaned_up == ["waiting"]
