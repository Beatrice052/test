"""Replay adapter for approved, redacted structured LLM recordings."""

from app.llm.fixture import FixtureLLMClient


class RecordedLLMClient(FixtureLLMClient):
    """A named replay boundary; recordings use the deterministic fixture format."""
