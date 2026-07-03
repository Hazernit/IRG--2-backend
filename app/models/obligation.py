from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, Date, Enum, Index, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.payment import Payment


class ObligationCategory(StrEnum):
    SUBSCRIPTION = "subscription"
    WARRANTY = "warranty"
    BILL = "bill"
    INSURANCE = "insurance"


class Recurrence(StrEnum):
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"


class ObligationStatus(StrEnum):
    ACTIVE = "active"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class Currency(StrEnum):
    RUB = "RUB"
    USD = "USD"
    EUR = "EUR"


def enum_values(enum_class: type[StrEnum]) -> list[str]:
    return [item.value for item in enum_class]


class Obligation(TimestampMixin, Base):
    __tablename__ = "obligations"
    __table_args__ = (
        CheckConstraint("amount > 0", name="positive_amount"),
        Index("ix_obligations_status_next_payment", "status", "next_payment_date"),
        Index("ix_obligations_category_status", "category", "status"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    currency: Mapped[Currency] = mapped_column(
        Enum(Currency, name="currency", values_callable=enum_values), nullable=False
    )
    category: Mapped[ObligationCategory] = mapped_column(
        Enum(
            ObligationCategory,
            name="obligation_category",
            values_callable=enum_values,
        ),
        nullable=False,
    )
    recurrence: Mapped[Recurrence | None] = mapped_column(
        Enum(Recurrence, name="recurrence", values_callable=enum_values), nullable=True
    )
    next_payment_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[ObligationStatus] = mapped_column(
        Enum(
            ObligationStatus,
            name="obligation_status",
            values_callable=enum_values,
        ),
        nullable=False,
        default=ObligationStatus.ACTIVE,
    )

    payments: Mapped[list["Payment"]] = relationship(
        back_populates="obligation",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
