"""Shared agent configuration with no tool or persistence surface."""

from dataclasses import dataclass

from app.llm.client import StructuredLLMClient


@dataclass(frozen=True, slots=True)
class AgentRuntime:
    llm: StructuredLLMClient
    system_prompt: str
    timeout_seconds: float = 30.0
