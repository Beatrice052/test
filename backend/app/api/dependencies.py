"""FastAPI dependencies resolved from the application composition root."""

from typing import cast

from fastapi import Request

from app.bootstrap import ApplicationContainer
from app.contracts.request import IdentityContext


def container(request: Request) -> ApplicationContainer:
    return cast(ApplicationContainer, request.app.state.container)


def identity(request: Request) -> IdentityContext:
    app_container = container(request)
    return app_container.identity_adapter.authenticate(request.headers)
