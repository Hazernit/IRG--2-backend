from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import system_clock
from app.db.session import get_session
from app.events.broker import event_broker
from app.repositories.obligations import SqlAlchemyObligationRepository
from app.services.obligations import ObligationService


def get_obligation_service(
    session: AsyncSession = Depends(get_session),
) -> ObligationService:
    return ObligationService(
        repository=SqlAlchemyObligationRepository(session),
        clock=system_clock,
        publisher=event_broker,
    )

