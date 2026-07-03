from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator

from app.models.obligation import Currency, ObligationCategory, ObligationStatus, Recurrence


Money = Annotated[Decimal, Field(gt=0, max_digits=14, decimal_places=2)]


class ObligationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=255)
    amount: Money
    currency: Currency
    category: ObligationCategory
    recurrence: Recurrence | None = None
    next_payment_date: date

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Название не может состоять только из пробелов")
        return normalized


class ObligationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    amount: Decimal
    currency: Currency
    category: ObligationCategory
    recurrence: Recurrence | None
    next_payment_date: date
    status: ObligationStatus
    created_at: datetime
    updated_at: datetime

    @field_serializer("amount", when_used="json")
    def serialize_amount(self, value: Decimal) -> float:
        return float(value)


class PaymentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    obligation_id: UUID
    amount: Decimal
    currency: Currency
    paid_at: datetime

    @field_serializer("amount", when_used="json")
    def serialize_amount(self, value: Decimal) -> float:
        return float(value)


class ObligationCreateResponse(BaseModel):
    obligation: ObligationRead
    warning: str | None = None


class PaymentResponse(BaseModel):
    obligation: ObligationRead
    payment: PaymentRead


class RenewalAlert(BaseModel):
    id: UUID
    title: str
    next_payment_date: date
    amount: Decimal
    currency: Currency

    @field_serializer("amount", when_used="json")
    def serialize_amount(self, value: Decimal) -> float:
        return float(value)


class UpcomingResponse(BaseModel):
    obligations: list[ObligationRead]
    totals: dict[Currency, Decimal]
    renewal_alerts: list[RenewalAlert]

    @field_serializer("totals", when_used="json")
    def serialize_totals(self, totals: dict[Currency, Decimal]) -> dict[str, Any]:
        return {currency.value: float(amount) for currency, amount in totals.items()}
