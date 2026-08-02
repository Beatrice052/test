"""Program-owned OpenSearch Gateway adapters."""

from app.gateway.base import OpenSearchGateway
from app.gateway.mock import MockOpenSearchGateway

__all__ = ["MockOpenSearchGateway", "OpenSearchGateway"]
