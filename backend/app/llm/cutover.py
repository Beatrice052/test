"""Fail-closed, credential-free checks for a real-LLM production cutover."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from app.contracts.common import StrictModel
from app.settings import AppSettings


class CutoverCheck(StrictModel):
    check_id: str
    status: Literal["PASSED", "FAILED"]
    detail: str


class RealLLMCutoverReport(StrictModel):
    status: Literal["PASSED", "FAILED"]
    checks: tuple[CutoverCheck, ...]
    credentials_in_report: Literal[False] = False


def evaluate_real_llm_cutover(
    settings: AppSettings,
    *,
    app_source_root: Path,
) -> RealLLMCutoverReport:
    """Validate live configuration and ensure Mock implementations remain isolated."""

    environment = settings.app_env.casefold()
    semantic_parts = {part.casefold() for part in settings.chatbi_semantic_package_dir.parts}
    semantic_input_parts = {part.casefold() for part in settings.chatbi_semantic_input_dir.parts}
    formal_files = tuple((app_source_root / "agents").glob("*.py")) + tuple(
        (app_source_root / "orchestration").glob("*.py")
    )
    forbidden_imports = (
        "app.llm.rule_based",
        "app.llm.fixture",
        "app.llm.recorded",
        "RuleBasedMockLLMClient",
        "FixtureLLMClient",
        "RecordedLLMClient",
    )
    polluted_files = [
        path.name
        for path in formal_files
        if any(token in path.read_text(encoding="utf-8") for token in forbidden_imports)
    ]
    orchestration_uses_text_parser = any(
        "parse_chart_preference" in path.read_text(encoding="utf-8")
        for path in (app_source_root / "orchestration").glob("*.py")
    )

    agent_sources = "\n".join(
        path.read_text(encoding="utf-8") for path in (app_source_root / "agents").glob("*.py")
    )
    required_operations = {
        'operation="turn_and_analysis_plan"',
        'operation="logical_query_plan"',
        'operation="post_query_visual_exploration"',
        'operation="post_query_insight_dashboard"',
    }
    query_agent = (app_source_root / "agents" / "logical_query_planner.py").read_text(
        encoding="utf-8"
    )
    phase3 = (app_source_root / "orchestration" / "phase3_nodes.py").read_text(encoding="utf-8")

    raw_checks = (
        (
            "live_environment",
            environment in {"mcp", "prod", "production"},
            "APP_ENV must be mcp/prod/production for a cutover.",
        ),
        (
            "live_llm_adapter",
            settings.chatbi_llm_mode == "openai_compatible",
            "CHATBI_LLM_MODE must be openai_compatible; Mock and recorded modes are forbidden.",
        ),
        (
            "llm_endpoint_configured",
            bool(settings.chatbi_llm_base_url),
            "CHATBI_LLM_BASE_URL must be injected at runtime.",
        ),
        (
            "llm_model_configured",
            bool(settings.chatbi_llm_model),
            "CHATBI_LLM_MODEL must identify an approved structured-output model.",
        ),
        (
            "trusted_identity",
            settings.chatbi_identity_mode == "trusted_headers",
            "The cutover profile must use trusted_headers identity.",
        ),
        (
            "mcp_gateway",
            settings.chatbi_gateway_mode == "mcp",
            "The formal data path must use the approved MCP Gateway.",
        ),
        (
            "non_mock_semantic_package",
            "mock" not in semantic_parts,
            "The formal profile must point at a reviewed non-Mock Semantic Package.",
        ),
        (
            "non_mock_semantic_input",
            "mock" not in semantic_input_parts,
            "The formal profile must compile only the reviewed non-Mock semantic input.",
        ),
        (
            "mock_adapter_isolation",
            not polluted_files,
            "Formal Agent/orchestration modules must not import concrete Mock/recorded adapters.",
        ),
        (
            "no_formal_text_intent_parser",
            not orchestration_uses_text_parser,
            "Formal orchestration must consume Agent A contracts, not text-rule parsers.",
        ),
        (
            "three_live_agent_operations",
            all(operation in agent_sources for operation in required_operations),
            "Agent A/B and both bounded Agent C passes must call StructuredLLMClient.generate().",
        ),
        (
            "compiler_owns_dsl",
            "query_dsl" not in query_agent and "self.compiler.compile" in phase3,
            "Agent B must output QueryPlanDraft while the deterministic compiler owns DSL.",
        ),
    )
    checks = tuple(
        CutoverCheck(
            check_id=check_id,
            status="PASSED" if passed else "FAILED",
            detail=detail if passed else f"ACTION REQUIRED: {detail}",
        )
        for check_id, passed, detail in raw_checks
    )
    return RealLLMCutoverReport(
        status="PASSED" if all(item.status == "PASSED" for item in checks) else "FAILED",
        checks=checks,
    )
