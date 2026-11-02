from datetime import datetime
from uuid import UUID

from sqlalchemy import func, insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from antifraud.domain.check import FraudCheck
from antifraud.domain.rules import Verdict
from antifraud.storage.tables import checks


class PostgresCheckHistory:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def lock_user(self, user_id: str) -> None:
        # Advisory lock держится до конца транзакции. Строки покупателя может ещё
        # не быть, поэтому блокируем не строку, а число, вычисленное из user_id.
        await self._session.execute(
            select(func.pg_advisory_xact_lock(func.hashtextextended(user_id, 0)))
        )

    async def find(self, order_id: UUID) -> FraudCheck | None:
        row = (
            await self._session.execute(select(checks).where(checks.c.order_id == order_id))
        ).first()
        if row is None:
            return None
        return FraudCheck(
            order_id=row.order_id,
            user_id=row.user_id,
            total_kopecks=row.total_kopecks,
            delivery_country=row.delivery_country,
            checked_at=row.checked_at,
            verdict=Verdict(score=row.score, reasons=tuple(row.reasons), approved=row.approved),
        )

    async def count_since(self, user_id: str, since: datetime) -> int:
        query = (
            select(func.count())
            .select_from(checks)
            .where(checks.c.user_id == user_id, checks.c.checked_at >= since)
        )
        return int(await self._session.scalar(query) or 0)

    async def approved_countries(self, user_id: str) -> frozenset[str]:
        # Страна отклонённого заказа «своей» не становится.
        result = await self._session.scalars(
            select(checks.c.delivery_country)
            .where(checks.c.user_id == user_id, checks.c.approved.is_(True))
            .distinct()
        )
        return frozenset(result)

    async def add(self, check: FraudCheck) -> None:
        await self._session.execute(
            insert(checks).values(
                order_id=check.order_id,
                user_id=check.user_id,
                total_kopecks=check.total_kopecks,
                delivery_country=check.delivery_country,
                checked_at=check.checked_at,
                score=check.verdict.score,
                reasons=list(check.verdict.reasons),
                approved=check.verdict.approved,
            )
        )
