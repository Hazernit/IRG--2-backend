from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status

from app.api.dependencies import get_obligation_service
from app.models.obligation import ObligationCategory, ObligationStatus
from app.schemas.obligation import (
    ObligationCreate,
    ObligationCreateResponse,
    ObligationRead,
    PaymentResponse,
    UpcomingResponse,
)
from app.services.obligations import ObligationService


router = APIRouter(prefix="/obligations", tags=["obligations"])
Service = Annotated[ObligationService, Depends(get_obligation_service)]


@router.post(
    "",
    response_model=ObligationCreateResponse,
    response_model_exclude_none=True,
    status_code=status.HTTP_201_CREATED,
)
async def create_obligation(
    payload: ObligationCreate,
    service: Service,
) -> ObligationCreateResponse:
    return await service.create(payload)


@router.get("", response_model=list[ObligationRead])
async def list_obligations(
    service: Service,
    category: ObligationCategory | None = None,
    status_filter: ObligationStatus | None = Query(default=None, alias="status"),
) -> list[ObligationRead]:
    return await service.list(category=category, status=status_filter)


@router.get("/upcoming", response_model=UpcomingResponse)
async def upcoming_obligations(
    service: Service,
    days: Annotated[int, Query(ge=0)] = 7,
) -> UpcomingResponse:
    return await service.upcoming(days)


@router.post("/{obligation_id}/pay", response_model=PaymentResponse)
async def pay_obligation(
    obligation_id: UUID,
    service: Service,
) -> PaymentResponse:
    return await service.pay(obligation_id)


@router.patch("/{obligation_id}/cancel", response_model=ObligationRead)
async def cancel_obligation(
    obligation_id: UUID,
    service: Service,
) -> ObligationRead:
    return await service.cancel(obligation_id)


@router.delete("/{obligation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_obligation(
    obligation_id: UUID,
    service: Service,
) -> Response:
    await service.delete(obligation_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

