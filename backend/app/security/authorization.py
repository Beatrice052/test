"""Small role gates; object ownership remains a repository responsibility."""

from app.contracts.request import IdentityContext


class AuthorizationError(PermissionError):
    pass


def require_role(identity: IdentityContext, role: str) -> None:
    if role not in identity.roles:
        raise AuthorizationError(f"required role is missing: {role}")
