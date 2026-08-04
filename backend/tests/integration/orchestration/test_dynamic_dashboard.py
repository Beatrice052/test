"""Dynamic dashboards follow the selected semantic roles instead of a fixed field template."""

from collections.abc import AsyncIterator
from pathlib import Path

import pytest

from app.bootstrap import ApplicationContainer, build_container
from app.contracts.progress import AnalysisProgressEvent
from app.contracts.request import ChatRequest, IdentityContext
from app.gateway.fixture_mock import FixtureBackedMockOpenSearchGateway
from app.settings import AppSettings

PROJECT_ROOT = Path(__file__).resolve().parents[4]


@pytest.fixture
async def container(tmp_path: Path) -> AsyncIterator[ApplicationContainer]:
    built = await build_container(
        AppSettings(
            app_database_url=f"sqlite:///{(tmp_path / 'chatbi.db').as_posix()}",
            app_checkpoint_path=tmp_path / "checkpoints.db",
            app_artifact_dir=tmp_path / "artifacts",
            chatbi_semantic_package_dir=PROJECT_ROOT / "compiled-semantic" / "mock",
            chatbi_llm_mode="rule_based",
            chatbi_gateway_mode="mock",
            chatbi_gateway_fixture_path=(
                PROJECT_ROOT / "fixtures" / "gateway" / "sub_message_rows.json"
            ),
        )
    )
    try:
        yield built
    finally:
        await built.close()


async def _ask(
    container: ApplicationContainer,
    message: str,
    turn_id: str,
    *,
    session_id: str | None = None,
):
    return await container.orchestrator.run(
        IdentityContext(subject_id="dynamic-dashboard-owner", roles=("analyst",)),
        ChatRequest(session_id=session_id, message=message, client_turn_id=turn_id),
        correlation_id=f"cor_{turn_id}",
    )


@pytest.mark.asyncio
async def test_recent_operational_question_builds_an_answer_first_dashboard(
    container: ApplicationContainer,
) -> None:
    gateway = container.gateway
    assert isinstance(gateway, FixtureBackedMockOpenSearchGateway)
    before = gateway.total_calls

    result = await _ask(
        container,
        "我想看下最近三个月的消息发送情况",
        "dynamic-overview-0001",
    )

    assert gateway.total_calls - before == 1
    assert result.answer is not None
    answer = result.answer
    plan = answer.analysis_plan
    assert plan is not None
    assert plan.scope.time_range.from_inclusive.month == 5
    assert plan.scope.time_range.to_exclusive.month == 8
    assert len(result.state["compiled_queries"]) == 1
    assert set(plan.tasks[0].dimension_ids) == {
        "sub_message.event_time",
        "sub_message.channel",
    }

    block_types = [item.type for item in answer.dashboard_spec.blocks]
    assert block_types[:2] == ["answer_summary", "kpi_group"]
    assert "insight_list" not in block_types
    assert "data_table" not in block_types
    assert "context_summary" in block_types
    assert "follow_up_suggestions" in block_types
    charts = [item for item in answer.dashboard_spec.blocks if item.type == "chart"]
    assert len(charts) == 3
    assert {item.visualization_intent for item in charts} == {
        "time_trend",
        "ranked_comparison",
        "composition",
    }
    assert all(item.description and item.evidence_refs for item in charts)

    kpi_block = next(item for item in answer.dashboard_spec.blocks if item.type == "kpi_group")
    assert {item.label for item in kpi_block.kpis} == {"消息记录数", "失败率"}
    assert len(kpi_block.kpis) == len(
        {
            item.metric_id
            for item in plan.metric_decisions
            if item.decision in {"required", "recommended"}
        }
    )
    summary = next(item for item in answer.dashboard_spec.blocks if item.type == "answer_summary")
    summary_text = str(summary.content.get("text"))
    assert "269" in summary_text
    assert "Validated results are ready" not in summary_text
    assert "消息记录数最高" in summary_text
    assert "期间峰值" in summary_text
    assert summary.insights == ()

    base = next(item for item in answer.dataset_bundle.datasets if item.kind == "base")
    assert answer.evidence_package is not None
    assert base.object_id in answer.evidence_package.business.data_tables
    assert all(item.passed for item in answer.dataset_bundle.reconciliation)


@pytest.mark.asyncio
async def test_compound_question_decomposes_goals_and_binds_each_chart_to_its_task(
    container: ApplicationContainer,
) -> None:
    result = await _ask(
        container,
        "分析2026年5月至7月各Channel消息量趋势、排名和状态构成",
        "compound-goals-0001",
    )

    assert result.answer is not None and result.answer.analysis_plan is not None
    answer = result.answer
    plan = answer.analysis_plan
    assert plan.scope.time_range.from_inclusive.isoformat().startswith("2026-05-01")
    assert plan.scope.time_range.to_exclusive.isoformat().startswith("2026-08-01")
    task_by_intent = {
        task.visualization_intents[0]: task for task in plan.tasks if task.visualization_intents
    }
    assert set(task_by_intent) == {"time_trend", "ranked_comparison", "composition"}
    assert len({task.task_id for task in plan.tasks}) == 3

    previews = {
        preview.visualization_intent: preview
        for preview in answer.visualization_previews
        if preview.decision != "REJECT"
    }
    assert set(previews) == {"time_trend", "ranked_comparison", "composition"}
    for intent, preview in previews.items():
        assert preview.task_ids == (task_by_intent[intent].task_id,)

    charts = [item for item in answer.dashboard_spec.blocks if item.type == "chart"]
    assert {item.visualization_intent for item in charts} == {
        "time_trend",
        "ranked_comparison",
        "composition",
    }
    assert all(
        item.chart_analysis is not None
        and item.chart_analysis.purpose
        and item.chart_analysis.reading_guide
        and item.chart_analysis.findings
        for item in charts
    )

    gateway = container.gateway
    assert isinstance(gateway, FixtureBackedMockOpenSearchGateway)
    calls_before_presentation_change = gateway.total_calls
    progress_events: list[AnalysisProgressEvent] = []

    async def collect_progress(event: AnalysisProgressEvent) -> None:
        progress_events.append(event)

    presentation = await container.orchestrator.run(
        IdentityContext(subject_id="dynamic-dashboard-owner", roles=("analyst",)),
        ChatRequest(
            session_id=result.session_id,
            message="把上一个结果改用点图展示",
            client_turn_id="compound-goals-dot-0002",
        ),
        correlation_id="cor_compound-goals-dot-0002",
        progress_callback=collect_progress,
    )
    assert presentation.answer is not None
    changed = presentation.answer
    assert changed.turn_kind.value == "PRESENTATION_CHANGE"
    assert changed.analytical_base_answer_id == answer.object_id
    assert changed.query_plan == answer.query_plan
    assert changed.dataset_bundle == answer.dataset_bundle
    assert changed.evidence_package == answer.evidence_package
    assert changed.visualization_previews == answer.visualization_previews
    assert gateway.total_calls == calls_before_presentation_change
    assert any(
        item.type == "chart" and item.chart_type == "dot" for item in changed.dashboard_spec.blocks
    )
    assert sum(item.type == "data_table" for item in changed.dashboard_spec.blocks) == 2
    emitted_stages = {item.stage for item in progress_events}
    assert {"query_plan", "dsl", "search", "analytics"}.isdisjoint(emitted_stages)
    assert any(item.safe_summary.get("execution_mode") == "reuse" for item in progress_events)


@pytest.mark.asyncio
async def test_error_reason_question_switches_to_its_actual_dimension(
    container: ApplicationContainer,
) -> None:
    result = await _ask(
        container,
        "最近三个月按错误码分析失败原因",
        "dynamic-errors-0001",
    )

    assert result.answer is not None and result.answer.analysis_plan is not None
    dimensions = set(result.answer.analysis_plan.tasks[0].dimension_ids)
    assert "sub_message.error_code" in dimensions
    assert "sub_message.event_time" in dimensions
    assert "sub_message.channel" not in dimensions
    grains = {
        item.grain for item in result.answer.dataset_bundle.datasets if item.kind == "derived"
    }
    assert ("sub_message.error_code",) in grains
    assert ("sub_message.event_time", "sub_message.error_code") in grains
    charts = [item for item in result.answer.dashboard_spec.blocks if item.type == "chart"]
    assert any("error code" in (item.title or "") for item in charts)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("message", "expected_type"),
    (
        ("请用折线图展示最近三个月的消息发送情况", "line"),
        ("请用热力图展示最近三个月的消息发送情况", "heatmap"),
    ),
)
async def test_explicit_compatible_chart_type_is_honored_in_the_initial_question(
    container: ApplicationContainer,
    message: str,
    expected_type: str,
) -> None:
    result = await _ask(container, message, f"explicit-{expected_type}-0001")

    assert result.answer is not None
    preference = result.answer.analysis_plan.presentation_preference
    assert preference.user_specified is True
    assert preference.requested_chart_type == expected_type
    charts = [item for item in result.answer.dashboard_spec.blocks if item.type == "chart"]
    assert charts
    assert {item.chart_type for item in charts} == {expected_type}
    if expected_type == "heatmap":
        assert len(charts) == 2
        assert {item.visualization_intent for item in charts} == {
            "time_trend",
            "composition",
        }


@pytest.mark.asyncio
async def test_explicit_table_request_uses_validated_tables_without_a_chart(
    container: ApplicationContainer,
) -> None:
    result = await _ask(
        container,
        "请用表格展示最近三个月的消息发送情况",
        "explicit-table-0001",
    )

    assert result.answer is not None
    assert not any(item.type == "chart" for item in result.answer.dashboard_spec.blocks)
    assert any(item.type == "data_table" for item in result.answer.dashboard_spec.blocks)
