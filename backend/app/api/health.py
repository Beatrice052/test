"""Liveness and readiness endpoints."""

from fastapi import APIRouter, Request

from app.bootstrap import ApplicationContainer

router = APIRouter(prefix="/api/v1/health", tags=["health"])


@router.get("/live")
async def live() -> dict[str, str]:
    """Report that the HTTP process is alive."""

    return {"status": "alive"}


@router.get("/ready")
async def ready(request: Request) -> dict[str, object]:
    """Report dependency readiness without running a business query."""

    container: ApplicationContainer = request.app.state.container
    return await container.readiness()
