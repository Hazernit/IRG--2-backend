from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.obligation import Currency, enum_values

if TYPE_CHECKING:
    from app.models.obligation import Obligation


class Payment(Base):
    __tablename__ = "payments"
    __table_args__ = (CheckConstraint("amount > 0", name="positive_amount"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    obligation_id: Mapped[UUID] = mapped_column(
        ForeignKey("obligations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    currency: Mapped[Currency] = mapped_column(
        Enum(Currency, name="currency", values_callable=enum_values, create_type=False),
        nullable=False,
    )
    paid_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    obligation: Mapped["Obligation"] = relationship(back_populates="payments")
