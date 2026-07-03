from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.api.routes import events, obligations
from app.services.errors import InvalidObligationStateError, ObligationNotFoundError


def create_app() -> FastAPI:
    application = FastAPI(
        title="Умный реестр подписок",
        description="Backend API для учёта подписок и регулярных платежей",
        version="1.0.0",
    )
    application.include_router(obligations.router)
    application.include_router(events.router)

    @application.get("/health", tags=["system"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @application.exception_handler(ObligationNotFoundError)
    async def obligation_not_found(
        request: Request, exc: ObligationNotFoundError
    ) -> JSONResponse:
        del request
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"detail": str(exc)},
        )

    @application.exception_handler(InvalidObligationStateError)
    async def invalid_obligation_state(
        request: Request, exc: InvalidObligationStateError
    ) -> JSONResponse:
        del request
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"detail": str(exc)},
        )

    return application


app = create_app()

