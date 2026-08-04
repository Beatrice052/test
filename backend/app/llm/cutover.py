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
    formal_python_roots = (
        "agents",
        "orchestration",
        "query",
        "analytics",
        "presentation",
    )
    formal_files = tuple(
        path for root in formal_python_roots for path in (app_source_root / root).rglob("*.py")
    ) + tuple((app_source_root / "agents" / "prompts").rglob("*.md"))
    forbidden_imports = (
        "app.llm.rule_based",
        "app.llm.fixture",
        "app.llm.recorded",
        "app.llm.mock_chart_preferences",
        "RuleBasedMockLLMClient",
        "FixtureLLMClient",
        "RecordedLLMClient",
        "parse_chart_preference",
    )
    polluted_files = [
        path.relative_to(app_source_root).as_posix()
        for path in formal_files
        if any(token in path.read_text(encoding="utf-8") for token in forbidden_imports)
    ]
    formal_path_uses_text_parser = any(
        "parse_chart_preference" in path.read_text(encoding="utf-8") for path in formal_files
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
    bootstrap_source = (app_source_root / "bootstrap.py").read_text(encoding="utf-8")
    fixed_task_bundle_tokens = (
        "task_time_trend",
        "task_ranked_comparison",
        "task_composition",
        'requested_intents.extend(("time_trend", "ranked_comparison", "composition"))',
    )
    formal_source = "\n".join(path.read_text(encoding="utf-8") for path in formal_files)

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
            "non_template_semantic_sources",
            not any(part.endswith("template") for part in semantic_parts | semantic_input_parts),
            "Formal runtime must use reviewed internal semantic input/package, never "
            "internal-template directly.",
        ),
        (
            "mock_adapter_isolation",
            not polluted_files,
            "Formal Agent, prompt, orchestration, query, analytics, and presentation modules "
            "must not import concrete Mock/recorded adapters.",
        ),
        (
            "no_formal_text_intent_parser",
            not formal_path_uses_text_parser,
            "The formal decision path must consume Agent contracts, not text-rule parsers.",
        ),
        (
            "no_fixed_analysis_task_bundle",
            not any(token in formal_source for token in fixed_task_bundle_tokens),
            "Formal Agent, prompt, orchestration, query, analytics, and presentation code must "
            "not hard-code the Mock trend/rank/composition task bundle.",
        ),
        (
            "three_live_agent_operations",
            all(operation in agent_sources for operation in required_operations),
            "Agent A/B and both bounded Agent C passes must call StructuredLLMClient.generate().",
        ),
        (
            "semantic_visualization_catalog_wired",
            "visualization_definitions=package.visualizations()" in bootstrap_source
            and "validator=AnalysisPlanValidator(" in bootstrap_source
            and "maximum_budget=maximum_analysis_budget" in bootstrap_source,
            "Agent A and its validator must consume the deployed Semantic Package's "
            "visualization catalog and server analysis budget.",
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
