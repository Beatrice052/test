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
    assert all(item.status == "PASSED" for item in report.checks)
    assert report.credentials_in_report is False
