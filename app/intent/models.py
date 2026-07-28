from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from app.agent.contracts import AnalysisPlan


class IntentModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ConversationContext(IntentModel):
    business_timezone: str
    pending_question: str | None = None
    pending_missing_slot: str | None = None
    original_question: str | None = None


class IntentOutcome(IntentModel):
    plan: AnalysisPlan | None = None
    clarification_question: str | None = None
    clarification_slot: str | None = None
    clarification_choices: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class LLMClient(Protocol):
    def create_analysis_plan(
        self, question: str, context: ConversationContext
    ) -> IntentOutcome: ...

    def summarize(self, question: str, prepared_data: dict, caveats: list[str]) -> str: ...
