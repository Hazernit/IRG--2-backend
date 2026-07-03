import pytest
from httpx import ASGITransport, AsyncClient

from app.api.dependencies import get_obligation_service
from app.main import create_app
from app.models.obligation import ObligationStatus, Recurrence
from app.services.obligations import ObligationService
from tests.conftest import FakeRepository, FixedClock, RecordingPublisher, make_obligation


@pytest.mark.asyncio
async def test_api_maps_invalid_state_to_422() -> None:
    repository = FakeRepository()
    obligation = repository.seed(
        make_obligation(status=ObligationStatus.EXPIRED, recurrence=Recurrence.MONTHLY)
    )
    service = ObligationService(repository, FixedClock(), RecordingPublisher())
    app = create_app()
    app.dependency_overrides[get_obligation_service] = lambda: service

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(f"/obligations/{obligation.id}/pay")

    assert response.status_code == 422
    assert response.json() == {"detail": "Оплатить можно только активное обязательство"}


@pytest.mark.asyncio
async def test_delete_api_returns_empty_204() -> None:
    repository = FakeRepository()
    obligation = repository.seed(make_obligation())
    service = ObligationService(repository, FixedClock(), RecordingPublisher())
    app = create_app()
    app.dependency_overrides[get_obligation_service] = lambda: service

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.delete(f"/obligations/{obligation.id}")

    assert response.status_code == 204
    assert response.content == b""

