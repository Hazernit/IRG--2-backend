from datetime import date, datetime
from typing import Protocol
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.obligation import (
    Obligation,
    ObligationCategory,
    ObligationStatus,
)
from app.models.payment import Payment


class ObligationRepository(Protocol):
    async def find_active_by_title(self, title: str) -> Obligation | None: ...

    async def add_obligation(self, obligation: Obligation) -> None: ...

    async def expire_overdue_one_time(self, today: date, now: datetime) -> None: ...

    async def list_obligations(
        self,
        category: ObligationCategory | None = None,
        status: ObligationStatus | None = None,
    ) -> list[Obligation]: ...

    async def list_upcoming(self, start: date, end: date) -> list[Obligation]: ...

    async def get(self, obligation_id: UUID, *, for_update: bool = False) -> Obligation | None: ...

    async def add_payment(self, payment: Payment) -> None: ...

    async def delete(self, obligation: Obligation) -> None: ...

    async def commit(self) -> None: ...

    async def refresh(self, instance: object) -> None: ...


class SqlAlchemyObligationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def find_active_by_title(self, title: str) -> Obligation | None:
        statement = select(Obligation).where(
            Obligation.status == ObligationStatus.ACTIVE,
            func.lower(Obligation.title) == title.lower(),
        )
        return await self.session.scalar(statement)

    async def add_obligation(self, obligation: Obligation) -> None:
        self.session.add(obligation)
        await self.session.flush()

    async def expire_overdue_one_time(self, today: date, now: datetime) -> None:
        statement = (
            update(Obligation)
            .where(
                Obligation.status == ObligationStatus.ACTIVE,
                Obligation.recurrence.is_(None),
                Obligation.next_payment_date < today,
            )
            .values(status=ObligationStatus.EXPIRED, updated_at=now)
        )
        await self.session.execute(statement)

    async def list_obligations(
        self,
        category: ObligationCategory | None = None,
        status: ObligationStatus | None = None,
    ) -> list[Obligation]:
        statement = select(Obligation)
        if category is not None:
            statement = statement.where(Obligation.category == category)
        if status is not None:
            statement = statement.where(Obligation.status == status)
        statement = statement.order_by(Obligation.next_payment_date.asc(), Obligation.id.asc())
        result = await self.session.scalars(statement)
        return list(result.all())

    async def list_upcoming(self, start: date, end: date) -> list[Obligation]:
        statement = (
            select(Obligation)
            .where(
                Obligation.status == ObligationStatus.ACTIVE,
                Obligation.next_payment_date >= start,
                Obligation.next_payment_date <= end,
            )
            .order_by(Obligation.next_payment_date.asc(), Obligation.id.asc())
        )
        result = await self.session.scalars(statement)
        return list(result.all())

    async def get(self, obligation_id: UUID, *, for_update: bool = False) -> Obligation | None:
        statement = select(Obligation).where(Obligation.id == obligation_id)
        if for_update:
            statement = statement.with_for_update()
        return await self.session.scalar(statement)

    async def add_payment(self, payment: Payment) -> None:
        self.session.add(payment)
        await self.session.flush()

    async def delete(self, obligation: Obligation) -> None:
        await self.session.delete(obligation)

    async def commit(self) -> None:
        await self.session.commit()

    async def refresh(self, instance: object) -> None:
        await self.session.refresh(instance)

