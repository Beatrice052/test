"""FastAPI application entry point."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app import __version__
from app.api.health import router as health_router
from app.api.workspace import router as workspace_router
from app.bootstrap import build_container
from app.persistence.errors import (
    IdempotencyConflict,
    OwnedObjectNotFound,
    SessionArchived,
    SessionLockConflict,
    VersionConflict,
)
from app.security.authorization import AuthorizationError
from app.security.identity import AuthenticationError
from app.settings import AppSettings, get_settings


def create_app(settings: AppSettings | None = None) -> FastAPI:
    """Create the application from explicit, testable dependencies."""

    resolved_settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        container = await build_container(resolved_settings)
        app.state.container = container
        try:
            yield
        finally:
            await container.close()

    app = FastAPI(
        title="OpenSearch ChatBI V6.1",
        version=__version__,
        lifespan=lifespan,
    )
    app.include_router(health_router)
    app.include_router(workspace_router)

    @app.exception_handler(OwnedObjectNotFound)
    async def owned_not_found(_: Request, error: OwnedObjectNotFound) -> JSONResponse:
        del error
        return JSONResponse(status_code=404, content={"code": "AUTH_OBJECT_NOT_FOUND"})

    @app.exception_handler(AuthenticationError)
    async def authentication_failed(_: Request, error: AuthenticationError) -> JSONResponse:
        return JSONResponse(
            status_code=401,
            content={"code": "AUTH_REQUIRED", "message": str(error)},
        )

    @app.exception_handler(AuthorizationError)
    async def authorization_failed(_: Request, error: AuthorizationError) -> JSONResponse:
        return JSONResponse(
            status_code=403,
            content={"code": "AUTH_FORBIDDEN", "message": str(error)},
        )

    @app.exception_handler(IdempotencyConflict)
    @app.exception_handler(VersionConflict)
    @app.exception_handler(SessionArchived)
    @app.exception_handler(SessionLockConflict)
    async def state_conflict(_: Request, error: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=409,
            content={"code": "SESSION_CONFLICT", "message": str(error)},
        )

    return app


app = create_app()
