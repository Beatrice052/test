"""G01-G25 executable acceptance matrix over credential-free adapters."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pytest

from app.bootstrap import ApplicationContainer, build_container
from app.contracts.request import ChatRequest, IdentityContext
from app.gateway.fixture_mock import FixtureBackedMockOpenSearchGateway
from app.persistence.answer_repository import AnswerRepository
from app.persistence.errors import OwnedObjectNotFound
from app.persistence.session_repository import SessionRepository
from app.semantic.retriever import SemanticRetriever
from app.settings import AppSettings

PROJECT_ROOT = Path(__file__).resolve().parents[3]
PACKAGE_DIR = PROJECT_ROOT / "compiled-semantic" / "mock"
CASES_PATH = PROJECT_ROOT / "evals" / "golden" / "cases.json"
CASES: list[dict[str, Any]] = json.loads(CASES_PATH.read_text(encoding="utf-8"))
BY_ID = {str(case["id"]): case for case in CASES}


@pytest.fixture
async def golden_container(tmp_path: Path) -> AsyncIterator[ApplicationContainer]:
    settings = AppSettings(
        app_database_url=f"sqlite:///{(tmp_path / 'chatbi.db').as_posix()}",
        app_checkpoint_path=tmp_path / "checkpoints.db",
        app_artifact_dir=tmp_path / "artifacts",
        chatbi_semantic_package_dir=PACKAGE_DIR,
        chatbi_llm_mode="rule_based",
        chatbi_gateway_mode="mock",
        chatbi_gateway_fixture_path=PROJECT_ROOT / "fixtures" / "gateway" / "sub_message_rows.json",
    )
    container = await build_container(settings)
    try:
        yield container
    finally:
        await container.close()


def _gateway(container: ApplicationContainer) -> FixtureBackedMockOpenSearchGateway:
    assert isinstance(container.gateway, FixtureBackedMockOpenSearchGateway)
    return container.gateway


async def _run(
    container: ApplicationContainer,
    case: dict[str, Any],
    *,
    session_id: str | None = None,
    subject_id: str = "golden-owner",
    client_turn_id: str | None = None,
):
    return await container.orchestrator.run(
        IdentityContext(subject_id=subject_id, roles=("analyst",)),
        ChatRequest(
            session_id=session_id,
            message=str(case["question"]),
            client_turn_id=client_turn_id or f"golden-{str(case['id']).lower()}-turn",
        ),
        correlation_id=f"cor_{str(case['id']).lower()}",
    )


def _assert_common(case: dict[str, Any], result: Any, gateway_delta: int) -> None:
    assert result.answer is not None, case["id"]
    assert result.answer.status.value == case["expected_status"], case["id"]
    assert gateway_delta == case["gateway_delta"], case["id"]
    assert result.state is not None, case["id"]
    decision = result.state["turn_decision"]
    assert decision.execution_mode == case["execution_mode"], case["id"]
    assert result.answer.session_id == result.session_id


def _assert_full_layers(case: dict[str, Any], result: Any) -> None:
    state = result.state
    answer = result.answer
    assert state is not None and answer is not None
    plan = state["analysis_plan"]
    resolved = state["resolved_analysis"]
    query_plan = state["query_plan"]
    compiled = state["compiled_queries"]
    bundle = state["dataset_bundle"]
    assert resolved.analysis_plan_id == plan.object_id
    assert query_plan.analysis_plan_id == plan.object_id
    assert compiled and all(query.query_plan_id == query_plan.object_id for query in compiled)
    assert all(query.query_dsl.get("size") == 0 for query in compiled)
    assert bundle.datasets and all(dataset.rows for dataset in bundle.datasets)
    assert bundle.data_qa and {item.rule_id for item in bundle.data_qa}
    assert answer.dataset_bundle == bundle
    assert answer.query_plan == query_plan
    assert answer.dashboard_spec is not None
    assert answer.evidence_package is not None
    assert answer.evidence_package.business.scope["analysis_goal"] == case["question"]
    assert answer.claims and all(claim.evidence_refs for claim in answer.claims)
    assert all(
        block.dataset_id is None
        or any(dataset.object_id == block.dataset_id for dataset in answer.dataset_bundle.datasets)
        for block in answer.dashboard_spec.blocks
    )
    serialized_dashboard = answer.dashboard_spec.model_dump_json()
    assert "raw_option" not in serialized_dashboard
    assert "renderItem" not in serialized_dashboard
    expected_metric = case.get("metric")
    if expected_metric is not None:
        assert any(decision.metric_id == expected_metric for decision in plan.metric_decisions), (
            case["id"]
        )
        assert any(expected_metric in query.semantics.metric_ids for query in compiled)
    expected_dimensions = set(case.get("dimensions", ()))
    planned_dimensions = {item for task in plan.tasks for item in task.dimension_ids}
    assert expected_dimensions.issubset(planned_dimensions), case["id"]
    expected_grain = set(case.get("grain", ()))
    planned_grain = {item for task in plan.tasks for item in task.grain}
    assert expected_grain.issubset(planned_grain), case["id"]
    if expected_metric == "failure_rate.v1":
        metric_rows = [
            row
            for dataset in bundle.datasets
            for row in dataset.rows
            if isinstance(row.values.get("metric_metadata"), dict)
        ]
        assert metric_rows
        for row in metric_rows:
            metadata = row.values["metric_metadata"]
            assert isinstance(metadata, dict)
            value = metadata.get("failure_rate")
            assert isinstance(value, dict)
            assert value["numerator"] is not None
            assert value["denominator"] is not None
            assert value["numerator"] <= value["denominator"]


def test_golden_manifest_is_exact_and_complete() -> None:
    assert [case["id"] for case in CASES] == [f"G{number:02d}" for number in range(1, 26)]
    required = {
        "id",
        "question",
        "category",
        "expected_status",
        "execution_mode",
        "gateway_delta",
    }
    assert all(required.issubset(case) for case in CASES)


PRIMARY_IDS = [f"G{number:02d}" for number in range(1, 13)] + [
    "G18",
    "G19",
    "G20",
    "G21",
    "G22",
]


@pytest.mark.parametrize("golden_id", PRIMARY_IDS)
async def test_primary_and_boundary_goldens(
    golden_id: str, golden_container: ApplicationContainer
) -> None:
    case = BY_ID[golden_id]
    gateway = _gateway(golden_container)
    before = gateway.total_calls
    result = await _run(golden_container, case)
    _assert_common(case, result, gateway.total_calls - before)

    if case["expected_status"] == "ANSWERED":
        _assert_full_layers(case, result)
    elif case["expected_status"] == "CLARIFICATION_REQUIRED":
        assert result.answer is not None and result.answer.analysis_plan is not None
        assert result.answer.analysis_plan.clarification is not None
        assert result.answer.analysis_plan.clarification.reason_code == case["reason_code"]
        assert result.answer.query_plan is None
    else:
        assert result.answer is not None
        assert result.answer.analysis_plan is None
        assert case["reason_code"] in result.answer.warnings

    if golden_id == "G01":
        definitions = result.answer.evidence_package.business.metric_definitions
        assert any("不自动称为去重发送量" in str(item) for item in definitions)
    if golden_id == "G02":
        candidate_ids = {
            item.item_id for item in result.state["semantic_candidates"].metric_candidates
        }
        assert {"message_record_count.v1", "failure_rate.v1"}.issubset(candidate_ids)
    if golden_id == "G03":
        base = next(
            dataset for dataset in result.answer.dataset_bundle.datasets if dataset.kind == "base"
        )
        rows = list(base.rows)
        assert all(
            "sub_message.event_time" in row.values and "sub_message.channel" in row.values
            for row in rows
        )
        assert len({str(row.values["sub_message.event_time"])[:7] for row in rows}) == 3
        derived_grains = {
            dataset.grain
            for dataset in result.answer.dataset_bundle.datasets
            if dataset.kind == "derived"
        }
        assert ("sub_message.event_time",) in derived_grains
        assert ("sub_message.channel",) in derived_grains
        assert ("sub_message.event_time", "sub_message.channel") in derived_grains
    if golden_id == "G05":
        assert any(claim.claim_type == "ranking" for claim in result.answer.claims)
    if golden_id == "G06":
        assert "Asia/Hong_Kong" in json.dumps(
            [item.query_dsl for item in result.state["compiled_queries"]]
        )
    if golden_id == "G07":
        assert len(result.state["query_plan"].steps) == 2
        assert result.state["query_plan"].steps[1].depends_on == ("q1_top_categories",)
    if golden_id == "G08":
        assert any(
            item.field_id == "sub_message.status"
            for item in result.state["analysis_plan"].scope.filters
        )
        if golden_id == "G09":
            # A Mock answer must not be mistaken for the real analyst. The formal
            # post-query selection is exercised by governed-tool contract tests and
            # real-LLM cutover goldens; this smoke case verifies that sparse data
            # still returns a truthful Dashboard rather than an invented anomaly.
            assert any(item.type == "chart" for item in result.answer.dashboard_spec.blocks)
    if golden_id == "G10":
        assert any(
            item.item_id == "sub_message.latency_ms"
            for item in result.state["semantic_candidates"].field_candidates
        )
    if golden_id == "G11":
        assert all(
            item.metric_id != "success_rate.v1"
            for item in result.state["analysis_plan"].metric_decisions
        )
    if golden_id == "G22":
        field = next(
            item
            for item in golden_container.semantic_package.fields()
            if item.field_id == "sub_message.free_text"
        )
        assert field.description is not None
        assert "ignore previous" not in field.description.casefold()
        report = golden_container.semantic_package.import_report()
        assert "sub_message.free_text" in report.sanitized_descriptions


@pytest.mark.parametrize("golden_id", ["G13", "G14", "G15", "G16"])
async def test_context_goldens(golden_id: str, golden_container: ApplicationContainer) -> None:
    base = await _run(golden_container, BY_ID["G05"], client_turn_id=f"base-{golden_id}")
    assert base.answer is not None
    session_id = base.session_id
    current = base
    gateway = _gateway(golden_container)
    previous = base
    for case_id in ("G13", "G14", "G15", "G16"):
        case = BY_ID[case_id]
        before = gateway.total_calls
        previous = current
        current = await _run(
            golden_container,
            case,
            session_id=session_id,
            client_turn_id=f"context-{golden_id}-{case_id}",
        )
        if case_id == golden_id:
            _assert_common(case, current, gateway.total_calls - before)
            break
    assert current.answer is not None
    if golden_id == "G13":
        assert current.answer.analysis_plan is not None
        assert any(item.values == ("SMS",) for item in current.answer.analysis_plan.scope.filters)
        assert current.answer.metric_versions == base.answer.metric_versions
    if golden_id == "G14":
        assert current.answer.analysis_plan is not None
        scope = current.answer.analysis_plan.scope
        assert scope.time_range.from_inclusive.month == 6
        assert any(item.values == ("SMS",) for item in scope.filters)
    if golden_id in {"G15", "G16"}:
        assert previous.answer is not None
        assert current.answer.dataset_bundle == previous.answer.dataset_bundle
        assert current.answer.evidence_package == previous.answer.evidence_package
        assert current.answer.analytical_base_answer_id is not None


@pytest.mark.parametrize("golden_id", ["G17", "G23", "G24", "G25"])
async def test_session_goldens(golden_id: str, golden_container: ApplicationContainer) -> None:
    gateway = _gateway(golden_container)
    case = BY_ID[golden_id]
    if golden_id == "G17":
        result = await _run(golden_container, case)
        _assert_common(case, result, 1)
        assert result.answer is not None and result.answer.analysis_plan is not None
        assert not result.answer.analysis_plan.scope.filters
        return

    seed_case = BY_ID["G04"]
    seed = await _run(golden_container, seed_case, client_turn_id=f"seed-{golden_id}")
    assert seed.answer is not None
    if golden_id == "G23":
        before = gateway.total_calls
        replay = await _run(
            golden_container,
            seed_case,
            session_id=seed.session_id,
            client_turn_id=f"seed-{golden_id}",
        )
        assert replay.answer == seed.answer
        assert gateway.total_calls - before == case["gateway_delta"]
        return

    sessions = SessionRepository(golden_container.database)
    answers = AnswerRepository(golden_container.database)
    if golden_id == "G24":
        with pytest.raises(OwnedObjectNotFound):
            sessions.get_session("another-user", seed.session_id)
        with pytest.raises(OwnedObjectNotFound):
            answers.get_answer("another-user", seed.answer.object_id)
        return

    restored_session = sessions.get_session("golden-owner", seed.session_id)
    restored_answer = answers.get_answer("golden-owner", seed.answer.object_id)
    assert restored_session.latest_answer_id == seed.answer.object_id
    assert restored_answer.dashboard_spec is not None
    assert restored_answer.dataset_bundle is not None
    assert restored_answer.evidence_package is not None
    dataset_id = restored_answer.dataset_bundle.datasets[0].object_id
    assert answers.get_dataset("golden-owner", dataset_id).rows
    retrieved = SemanticRetriever(PACKAGE_DIR).retrieve("7月各Channel失败率")
    assert retrieved.metric_candidates
