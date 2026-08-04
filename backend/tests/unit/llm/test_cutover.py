import shutil
from pathlib import Path

from app.llm.cutover import evaluate_real_llm_cutover
from app.settings import AppSettings

APP_SOURCE = Path(__file__).resolve().parents[3] / "app"


def test_real_llm_cutover_passes_only_with_live_config_and_isolated_mock() -> None:
    settings = AppSettings(
        app_env="mcp",
        chatbi_identity_mode="trusted_headers",
        chatbi_llm_mode="openai_compatible",
        chatbi_llm_base_url="https://llm.internal/v1",
        chatbi_llm_model="approved-structured-model",
        chatbi_gateway_mode="mcp",
        chatbi_semantic_package_dir="../compiled-semantic/internal",
        chatbi_semantic_input_dir="../semantic-input/internal",
    )

    report = evaluate_real_llm_cutover(settings, app_source_root=APP_SOURCE)

    assert report.status == "PASSED"
    assert len(report.checks) == 15
    assert all(item.status == "PASSED" for item in report.checks)
    assert {item.check_id for item in report.checks}.issuperset(
        {
            "non_template_semantic_sources",
            "no_fixed_analysis_task_bundle",
            "semantic_visualization_catalog_wired",
        }
    )
    assert report.credentials_in_report is False


def test_real_llm_cutover_rejects_rule_pollution_outside_orchestration(
    tmp_path: Path,
) -> None:
    app_source = tmp_path / "app"
    shutil.copytree(APP_SOURCE, app_source)
    (app_source / "presentation" / "polluted.py").write_text(
        "from app.llm.rule_based import RuleBasedMockLLMClient\n",
        encoding="utf-8",
    )
    (app_source / "agents" / "prompts" / "polluted.md").write_text(
        "Always create task_time_trend.\n",
        encoding="utf-8",
    )
    settings = AppSettings(
        app_env="mcp",
        chatbi_identity_mode="trusted_headers",
        chatbi_llm_mode="openai_compatible",
        chatbi_llm_base_url="https://llm.internal/v1",
        chatbi_llm_model="approved-structured-model",
        chatbi_gateway_mode="mcp",
        chatbi_semantic_package_dir="../compiled-semantic/internal",
        chatbi_semantic_input_dir="../semantic-input/internal",
    )

    report = evaluate_real_llm_cutover(settings, app_source_root=app_source)
    checks = {item.check_id: item.status for item in report.checks}

    assert report.status == "FAILED"
    assert checks["mock_adapter_isolation"] == "FAILED"
    assert checks["no_fixed_analysis_task_bundle"] == "FAILED"
