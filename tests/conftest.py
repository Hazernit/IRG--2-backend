from datetime import date, datetime, timezone
from typing import Any
from uuid import UUID, uuid4

import pytest

from app.models.obligation import (
    Currency,
    Obligation,
    ObligationCategory,
    ObligationStatus,
    Recurrence,
)
from app.models.payment import Payment


FIXED_TODAY = date(2025, 2, 1)
FIXED_NOW = datetime(2025, 2, 1, 12, 0, tzinfo=timezone.utc)


class FixedClock:
    def today(self) -> date:
        return FIXED_TODAY

    def now(self) -> datetime:
        return FIXED_NOW


class RecordingPublisher:
    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    async def publish(self, event: dict[str, Any]) -> None:
        self.events.append(event)


class FakeRepository:
    """In-memory test double: business tests never connect to a database."""

    def __init__(self) -> None:
        self.obligations: dict[UUID, Obligation] = {}
        self.payments: list[Payment] = []

    def seed(self, obligation: Obligation) -> Obligation:
        self._set_obligation_defaults(obligation)
        self.obligations[obligation.id] = obligation
        return obligation

    async def find_active_by_title(self, title: str) -> Obligation | None:
        return next(
            (
                item
                for item in self.obligations.values()
                if item.status == ObligationStatus.ACTIVE
                and item.title.lower() == title.lower()
            ),
            None,
        )

    async def add_obligation(self, obligation: Obligation) -> None:
        self.seed(obligation)

    async def expire_overdue_one_time(self, today: date, now: datetime) -> None:
        for obligation in self.obligations.values():
            if (
                obligation.status == ObligationStatus.ACTIVE
                and obligation.recurrence is None
                and obligation.next_payment_date < today
            ):
                obligation.status = ObligationStatus.EXPIRED
                obligation.updated_at = now

    async def list_obligations(
        self,
        category: ObligationCategory | None = None,
        status: ObligationStatus | None = None,
    ) -> list[Obligation]:
        result = [
            obligation
            for obligation in self.obligations.values()
            if (category is None or obligation.category == category)
            and (status is None or obligation.status == status)
        ]
        return sorted(result, key=lambda item: (item.next_payment_date, str(item.id)))

    async def list_upcoming(self, start: date, end: date) -> list[Obligation]:
        result = [
            obligation
            for obligation in self.obligations.values()
            if obligation.status == ObligationStatus.ACTIVE
            and start <= obligation.next_payment_date <= end
        ]
        return sorted(result, key=lambda item: (item.next_payment_date, str(item.id)))

    async def get(self, obligation_id: UUID, *, for_update: bool = False) -> Obligation | None:
        del for_update
        return self.obligations.get(obligation_id)

    async def add_payment(self, payment: Payment) -> None:
        if payment.id is None:
            payment.id = uuid4()
        self.payments.append(payment)

    async def delete(self, obligation: Obligation) -> None:
        self.obligations.pop(obligation.id)
        self.payments = [
            payment for payment in self.payments if payment.obligation_id != obligation.id
        ]

    async def commit(self) -> None:
        return None

    async def refresh(self, instance: object) -> None:
        if isinstance(instance, Obligation):
            instance.updated_at = FIXED_NOW

    @staticmethod
    def _set_obligation_defaults(obligation: Obligation) -> None:
        if obligation.id is None:
            obligation.id = uuid4()
        if obligation.created_at is None:
            obligation.created_at = FIXED_NOW
        if obligation.updated_at is None:
            obligation.updated_at = FIXED_NOW


def make_obligation(
    *,
    title: str = "Test",
    amount: str = "100.00",
    currency: Currency = Currency.RUB,
    category: ObligationCategory = ObligationCategory.SUBSCRIPTION,
    recurrence: Recurrence | None = None,
    next_payment_date: date = FIXED_TODAY,
    status: ObligationStatus = ObligationStatus.ACTIVE,
) -> Obligation:
    from decimal import Decimal

    return Obligation(
        id=uuid4(),
        title=title,
        amount=Decimal(amount),
        currency=currency,
        category=category,
        recurrence=recurrence,
        next_payment_date=next_payment_date,
        status=status,
        created_at=FIXED_NOW,
        updated_at=FIXED_NOW,
    )


@pytest.fixture
def repository() -> FakeRepository:
    return FakeRepository()


@pytest.fixture
def publisher() -> RecordingPublisher:
    return RecordingPublisher()

