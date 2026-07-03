from collections import defaultdict
from datetime import timedelta
from decimal import Decimal
from uuid import UUID

from dateutil.relativedelta import relativedelta

from app.core.clock import Clock
from app.events.broker import EventPublisher
from app.models.obligation import (
    Currency,
    Obligation,
    ObligationCategory,
    ObligationStatus,
    Recurrence,
)
from app.models.payment import Payment
from app.repositories.obligations import ObligationRepository
from app.schemas.obligation import (
    ObligationCreate,
    ObligationCreateResponse,
    PaymentResponse,
    RenewalAlert,
    UpcomingResponse,
)
from app.services.errors import InvalidObligationStateError, ObligationNotFoundError


DUPLICATE_WARNING = "Активное обязательство с таким названием уже существует"


class ObligationService:
    def __init__(
        self,
        repository: ObligationRepository,
        clock: Clock,
        publisher: EventPublisher,
    ) -> None:
        self.repository = repository
        self.clock = clock
        self.publisher = publisher

    async def create(self, data: ObligationCreate) -> ObligationCreateResponse:
        duplicate = await self.repository.find_active_by_title(data.title)
        status = (
            ObligationStatus.EXPIRED
            if data.next_payment_date < self.clock.today()
            else ObligationStatus.ACTIVE
        )
        obligation = Obligation(
            title=data.title,
            amount=data.amount,
            currency=data.currency,
            category=data.category,
            recurrence=data.recurrence,
            next_payment_date=data.next_payment_date,
            status=status,
        )
        await self.repository.add_obligation(obligation)
        await self.repository.commit()
        await self.repository.refresh(obligation)
        return ObligationCreateResponse(
            obligation=obligation,
            warning=DUPLICATE_WARNING if duplicate is not None else None,
        )

    async def list(
        self,
        category: ObligationCategory | None = None,
        status: ObligationStatus | None = None,
    ) -> list[Obligation]:
        await self.repository.expire_overdue_one_time(self.clock.today(), self.clock.now())
        await self.repository.commit()
        return await self.repository.list_obligations(category=category, status=status)

    async def upcoming(self, days: int) -> UpcomingResponse:
        start = self.clock.today()
        obligations = await self.repository.list_upcoming(start, start + timedelta(days=days))

        totals: defaultdict[Currency, Decimal] = defaultdict(lambda: Decimal("0"))
        alerts: list[RenewalAlert] = []
        for obligation in obligations:
            totals[obligation.currency] += obligation.amount
            if (
                obligation.category == ObligationCategory.SUBSCRIPTION
                and obligation.recurrence is not None
            ):
                alerts.append(RenewalAlert.model_validate(obligation, from_attributes=True))

        return UpcomingResponse(
            obligations=obligations,
            totals=dict(totals),
            renewal_alerts=alerts,
        )

    async def pay(self, obligation_id: UUID) -> PaymentResponse:
        obligation = await self._get(obligation_id, for_update=True)
        if obligation.status != ObligationStatus.ACTIVE:
            raise InvalidObligationStateError(
                "Оплатить можно только активное обязательство"
            )

        payment = Payment(
            obligation_id=obligation.id,
            amount=obligation.amount,
            currency=obligation.currency,
            paid_at=self.clock.now(),
        )
        if obligation.recurrence == Recurrence.MONTHLY:
            obligation.next_payment_date += relativedelta(months=1)
        elif obligation.recurrence == Recurrence.QUARTERLY:
            obligation.next_payment_date += relativedelta(months=3)
        elif obligation.recurrence == Recurrence.YEARLY:
            obligation.next_payment_date += relativedelta(years=1)
        else:
            obligation.status = ObligationStatus.CANCELLED

        await self.repository.add_payment(payment)
        await self.repository.commit()
        await self.repository.refresh(obligation)
        await self.repository.refresh(payment)
        return PaymentResponse(obligation=obligation, payment=payment)

    async def cancel(self, obligation_id: UUID) -> Obligation:
        obligation = await self._get(obligation_id, for_update=True)
        if obligation.status != ObligationStatus.ACTIVE:
            raise InvalidObligationStateError(
                "Отменить можно только активное обязательство"
            )
        obligation.status = ObligationStatus.CANCELLED
        await self.repository.commit()
        await self.repository.refresh(obligation)
        return obligation

    async def delete(self, obligation_id: UUID) -> None:
        obligation = await self._get(obligation_id, for_update=True)
        await self.repository.delete(obligation)
        await self.repository.commit()
        await self.publisher.publish(
            {"type": "obligation_deleted", "id": str(obligation_id)}
        )

    async def _get(self, obligation_id: UUID, *, for_update: bool) -> Obligation:
        obligation = await self.repository.get(obligation_id, for_update=for_update)
        if obligation is None:
            raise ObligationNotFoundError
        return obligation

