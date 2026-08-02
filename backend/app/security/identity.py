"""Identity adapters; repositories still enforce ownership in SQL."""

from collections.abc import Mapping
from typing import Protocol

from app.contracts.request import IdentityContext


class AuthenticationError(PermissionError):
    pass


class IdentityAdapter(Protocol):
    def authenticate(self, headers: Mapping[str, str]) -> IdentityContext: ...


class StaticMockIdentityAdapter:
    """Credential-free identity for the explicit local/mock profile only."""

    def __init__(self, subject_id: str = "mock-user") -> None:
        self.subject_id = subject_id

    def authenticate(self, headers: Mapping[str, str]) -> IdentityContext:
        subject_id = headers.get("x-mock-subject", self.subject_id).strip() or self.subject_id
        roles = tuple(
            role.strip()
            for role in headers.get("x-mock-roles", "analyst").split(",")
            if role.strip()
        )
        return IdentityContext(subject_id=subject_id, roles=roles)


class TrustedHeaderIdentityAdapter:
    """Read identity only after an approved reverse proxy has authenticated it."""

    def authenticate(self, headers: Mapping[str, str]) -> IdentityContext:
        subject_id = headers.get("x-authenticated-subject", "").strip()
        if not subject_id:
            raise AuthenticationError("authenticated subject header is missing")
        roles = tuple(
            role.strip()
            for role in headers.get("x-authenticated-roles", "").split(",")
            if role.strip()
        )
        return IdentityContext(subject_id=subject_id, roles=roles)
