from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


def utc_now() -> datetime:
    return datetime.now(UTC)


class MessageRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class MessageKind(StrEnum):
    QUESTION = "question"
    ANSWER = "answer"
    CLARIFICATION = "clarification"
    ERROR = "error"
    BLOCKED = "blocked"


class ChatMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message_id: str
    role: MessageRole
    kind: MessageKind
    content: str
    created_at: datetime = Field(default_factory=utc_now)
    run_id: str | None = None


class PendingClarification(BaseModel):
    model_config = ConfigDict(extra="forbid")

    clarification_id: str
    question: str
    missing_slot: str
    allowed_choices: list[str] = Field(default_factory=list)
    partial_analysis_plan: dict[str, Any]
    original_user_question: str
    created_at: datetime = Field(default_factory=utc_now)


class SessionState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    messages: list[ChatMessage] = Field(default_factory=list)
    pending_clarification: PendingClarification | None = None
    last_analysis_plan: dict[str, Any] | None = None
    last_query_plan: dict[str, Any] | None = None
    last_run_id: str | None = None
