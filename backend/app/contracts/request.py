"""API request and identity contracts."""

from typing import Literal

from pydantic import Field

from app.contracts.common import StrictModel


class IdentityContext(StrictModel):
    subject_id: str = Field(min_length=1, max_length=256)
    roles: tuple[str, ...] = ()
    workspace_id: str = Field(default="default", min_length=1, max_length=128)
    locale: str = Field(default="zh-CN", min_length=2, max_length=16)


class ChatRequest(StrictModel):
    session_id: str | None = Field(default=None, pattern=r"^ses_[a-zA-Z0-9_-]+$")
    message: str = Field(min_length=1, max_length=8000)
    client_turn_id: str = Field(min_length=8, max_length=128)
    mode: Literal["standard", "debug"] = "standard"
