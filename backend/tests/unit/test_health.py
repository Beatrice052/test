"""Phase 0 API smoke tests."""

from httpx import ASGITransport, AsyncClient

from app.main import create_app
from app.settings import AppSettings


async def test_liveness() -> None:
    app = create_app(AppSettings())
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client,
    ):
        response = await client.get("/api/v1/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "alive"}


async def test_mock_profile_is_ready_without_credentials() -> None:
    settings = AppSettings(chatbi_llm_mode="fixture", chatbi_gateway_mode="mock")
    app = create_app(settings)

    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client,
    ):
        response = await client.get("/api/v1/health/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "profile": "mock",
        "llm_mode": "fixture",
        "gateway_mode": "mock",
    }
