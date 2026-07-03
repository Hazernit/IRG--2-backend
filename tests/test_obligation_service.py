from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.models.obligation import (
    Currency,
    ObligationCategory,
    ObligationStatus,
    Recurrence,
)
from app.models.payment import Payment
from app.schemas.obligation import ObligationCreate
from app.services.errors import InvalidObligationStateError, ObligationNotFoundError
from app.services.obligations import DUPLICATE_WARNING, ObligationService
from tests.conftest import (
    FIXED_NOW,
    FIXED_TODAY,
    FakeRepository,
    FixedClock,
    RecordingPublisher,
    make_obligation,
)


def build_service(
    repository: FakeRepository, publisher: RecordingPublisher
) -> ObligationService:
    return ObligationService(repository, FixedClock(), publisher)


@pytest.mark.asyncio
async def test_create_past_obligation_as_expired(
    repository: FakeRepository, publisher: RecordingPublisher
) -> None:
    service = build_service(repository, publisher)

    result = await service.create(
        ObligationCreate(
            title="Старый чек",
            amount="500.00",
            currency=Currency.RUB,
            category=ObligationCategory.BILL,
            recurrence=None,
            next_payment_date=FIXED_TODAY - timedelta(days=1),
        )
    )

    assert result.obligation.status == ObligationStatus.EXPIRED
    assert result.warning is None


@pytest.mark.asyncio
async def test_create_case_insensitive_duplicate_with_warning(
    repository: FakeRepository, publisher: RecordingPublisher
) -> None:
    repository.seed(make_obligation(title="Netflix", recurrence=Recurrence.MONTHLY))
    service = build_service(repository, publisher)

    result = await service.create(
        ObligationCreate(
            title="nEtFlIx",
            amount="9.99",
            currency=Currency.USD,
            category=ObligationCategory.SUBSCRIPTION,
            recurrence=Recurrence.MONTHLY,
            next_payment_date=FIXED_TODAY,
        )
    )

    assert result.warning == DUPLICATE_WARNING
    assert len(repository.obligations) == 2


@pytest.mark.asyncio
async def test_lazy_expiry_skips_recurring_and_applies_both_filters(
    repository: FakeRepository, publisher: RecordingPublisher
) -> None:
    one_time = repository.seed(
        make_obligation(
            title="Просроченный счёт",
            category=ObligationCategory.BILL,
            next_payment_date=FIXED_TODAY - timedelta(days=2),
        )
    )
    recurring = repository.seed(
        make_obligation(
            title="Просроченная дата подписки",
            recurrence=Recurrence.MONTHLY,
            next_payment_date=FIXED_TODAY - timedelta(days=3),
        )
    )
    repository.seed(
        make_obligation(
            title="Будущая подписка",
            recurrence=Recurrence.YEARLY,
            next_payment_date=FIXED_TODAY + timedelta(days=2),
        )
    )
    service = build_service(repository, publisher)

    result = await service.list(
        category=ObligationCategory.SUBSCRIPTION,
        status=ObligationStatus.ACTIVE,
    )

    assert one_time.status == ObligationStatus.EXPIRED
    assert recurring.status == ObligationStatus.ACTIVE
    assert [item.title for item in result] == [
        "Просроченная дата подписки",
        "Будущая подписка",
    ]


@pytest.mark.parametrize(
    ("recurrence", "start", "expected_date", "expected_status"),
    [
        (Recurrence.MONTHLY, date(2025, 1, 31), date(2025, 2, 28), ObligationStatus.ACTIVE),
        (Recurrence.QUARTERLY, date(2025, 1, 31), date(2025, 4, 30), ObligationStatus.ACTIVE),
        (Recurrence.YEARLY, date(2024, 2, 29), date(2025, 2, 28), ObligationStatus.ACTIVE),
        (None, date(2025, 2, 1), date(2025, 2, 1), ObligationStatus.CANCELLED),
    ],
)
@pytest.mark.asyncio
async def test_pay_for_every_recurrence(
    recurrence: Recurrence | None,
    start: date,
    expected_date: date,
    expected_status: ObligationStatus,
    repository: FakeRepository,
    publisher: RecordingPublisher,
) -> None:
    obligation = repository.seed(
        make_obligation(recurrence=recurrence, next_payment_date=start, amount="199.90")
    )
    service = build_service(repository, publisher)

    result = await service.pay(obligation.id)

    assert result.obligation.next_payment_date == expected_date
    assert result.obligation.status == expected_status
    assert result.payment.amount == Decimal("199.90")
    assert result.payment.currency == Currency.RUB
    assert result.payment.paid_at == FIXED_NOW


@pytest.mark.parametrize(
    "status", [ObligationStatus.EXPIRED, ObligationStatus.CANCELLED]
)
@pytest.mark.asyncio
async def test_cannot_pay_non_active_obligation(
    status: ObligationStatus,
    repository: FakeRepository,
    publisher: RecordingPublisher,
) -> None:
    obligation = repository.seed(make_obligation(status=status))
    service = build_service(repository, publisher)

    with pytest.raises(InvalidObligationStateError, match="только активное"):
        await service.pay(obligation.id)

    assert repository.payments == []


@pytest.mark.parametrize(
    "status", [ObligationStatus.EXPIRED, ObligationStatus.CANCELLED]
)
@pytest.mark.asyncio
async def test_cannot_cancel_non_active_obligation(
    status: ObligationStatus,
    repository: FakeRepository,
    publisher: RecordingPublisher,
) -> None:
    obligation = repository.seed(make_obligation(status=status))
    service = build_service(repository, publisher)

    with pytest.raises(InvalidObligationStateError, match="только активное"):
        await service.cancel(obligation.id)


@pytest.mark.asyncio
async def test_upcoming_is_inclusive_and_returns_totals_and_alerts(
    repository: FakeRepository, publisher: RecordingPublisher
) -> None:
    first = repository.seed(
        make_obligation(
            title="Музыка",
            amount="100.00",
            recurrence=Recurrence.MONTHLY,
            next_payment_date=FIXED_TODAY,
        )
    )
    repository.seed(
        make_obligation(
            title="Счёт",
            amount="50.00",
            category=ObligationCategory.BILL,
            next_payment_date=FIXED_TODAY + timedelta(days=7),
        )
    )
    second = repository.seed(
        make_obligation(
            title="Видео",
            amount="9.99",
            currency=Currency.USD,
            recurrence=Recurrence.YEARLY,
            next_payment_date=FIXED_TODAY + timedelta(days=3),
        )
    )
    repository.seed(
        make_obligation(next_payment_date=FIXED_TODAY + timedelta(days=8))
    )
    repository.seed(
        make_obligation(
            title="Отменённая",
            status=ObligationStatus.CANCELLED,
            next_payment_date=FIXED_TODAY + timedelta(days=1),
        )
    )
    service = build_service(repository, publisher)

    result = await service.upcoming(7)

    assert len(result.obligations) == 3
    assert result.totals == {Currency.RUB: Decimal("150.00"), Currency.USD: Decimal("9.99")}
    assert [alert.id for alert in result.renewal_alerts] == [first.id, second.id]


@pytest.mark.asyncio
async def test_delete_removes_payments_and_publishes_event_afterward(
    repository: FakeRepository, publisher: RecordingPublisher
) -> None:
    obligation = repository.seed(make_obligation(status=ObligationStatus.CANCELLED))
    repository.payments.append(
        Payment(
            id=obligation.id,
            obligation_id=obligation.id,
            amount=obligation.amount,
            currency=obligation.currency,
            paid_at=FIXED_NOW,
        )
    )
    service = build_service(repository, publisher)

    await service.delete(obligation.id)

    assert obligation.id not in repository.obligations
    assert repository.payments == []
    assert publisher.events == [
        {"type": "obligation_deleted", "id": str(obligation.id)}
    ]


@pytest.mark.asyncio
async def test_missing_obligation_returns_domain_not_found(
    repository: FakeRepository, publisher: RecordingPublisher
) -> None:
    from uuid import uuid4

    service = build_service(repository, publisher)

    with pytest.raises(ObligationNotFoundError):
        await service.pay(uuid4())

