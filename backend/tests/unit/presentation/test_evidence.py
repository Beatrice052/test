"""Evidence separates business/advanced layers and CSV export prevents formula injection."""

import hashlib
import json
from pathlib import Path

import pytest

from app.analytics.bundle import DatasetBundleBuilder
from app.contracts.dataset import DataQARecord
from app.contracts.execution import RawSearchResult, ShardSummary
from app.contracts.request import IdentityContext
from app.gateway.executor import GatewayExecutor
from app.gateway.mock import MockOpenSearchGateway
from app.presentation.artifacts import EvidenceArtifactError, EvidenceArtifactStore
from app.presentation.evidence import EvidenceAccessPolicy, EvidenceBuilder, EvidenceExporter
from app.query.compiler import DslCompiler
from tests.integration.query.test_plan_compile import _plans
from tests.unit.analytics.test_metric_qa import _derive


@pytest.mark.asyncio
async def test_evidence_business_layer_has_no_dsl_and_advanced_is_snapshot_backed() -> None:
    package, analysis, _, _, plan, _ = await _plans("查询2026年7月各Channel失败率")
    query = DslCompiler(fields=package.fields(), metrics=package.metrics()).compile(
        plan, plan.steps[0].step_id
    )
    raw = RawSearchResult(
        query_id=query.object_id,
        took_ms=2,
        timed_out=False,
        shards=ShardSummary(total=1, successful=1, skipped=0, failed=0),
        aggregations={},
        raw_size_bytes=32,
    )
    gateway = MockOpenSearchGateway()
    gateway.register(query.query_fingerprint, raw)
    execution = await GatewayExecutor(gateway, mode="mock").execute(query)
    derived = _derive()
    bundle = DatasetBundleBuilder().build((derived.dataset,), reconciliation=derived.reconciliation)
    evidence = EvidenceBuilder().build(
        analysis_plan=analysis,
        query_plan=plan,
        compiled_queries=(query,),
        executions=(execution.record,),
        bundle=bundle,
        metric_definitions=package.metrics(),
        semantic_package_version=package.manifest.package_version,
    )
    business_json = json.dumps(evidence.business.model_dump(mode="json"))
    advanced_json = json.dumps(evidence.advanced.model_dump(mode="json"))
    assert "query_dsl" not in business_json
    assert "query_dsl" in advanced_json
    assert evidence.business.data_tables == (derived.dataset.object_id,)
    assert evidence.business.downloads[0].endswith("/csv")
    assert "credentials" in evidence.redaction.removed_fields
    assert evidence.business.quality == ()
    assert evidence.business.quality_summary is not None


def test_csv_export_quotes_nested_metadata_and_neutralizes_formula_cells() -> None:
    dataset = _derive().dataset
    first = dataset.rows[0]
    injected = first.model_copy(
        update={"values": {**first.values, "sub_message.channel": "=cmd|' /C calc'!A0"}}
    )
    altered = dataset.model_copy(update={"rows": (injected, *dataset.rows[1:])})
    exported = EvidenceExporter().dataset_csv(altered)
    assert "'=cmd" in exported
    assert '"{""failure_rate""' in exported
    assert exported.splitlines()[0].startswith("row_id,sub_message.channel")


def test_evidence_layer_access_is_role_gated() -> None:
    policy = EvidenceAccessPolicy()
    assert not policy.allow_advanced(IdentityContext(subject_id="business"))
    assert policy.allow_advanced(IdentityContext(subject_id="analyst", roles=("analyst",)))
    assert not policy.allow_debug(IdentityContext(subject_id="analyst", roles=("analyst",)))
    assert policy.allow_debug(IdentityContext(subject_id="dev", roles=("developer",)))

    internal = _derive().dataset
    restricted = internal.model_copy(
        update={
            "columns": (
                internal.columns[0].model_copy(update={"security_classification": "restricted"}),
                *internal.columns[1:],
            )
        }
    )
    assert policy.allow_csv(IdentityContext(subject_id="business"), internal)
    assert not policy.allow_csv(
        IdentityContext(subject_id="analyst", roles=("analyst",)), restricted
    )
    assert policy.allow_csv(IdentityContext(subject_id="dev", roles=("developer",)), restricted)


@pytest.mark.asyncio
async def test_user_quality_summary_excludes_pass_checklist_but_keeps_material_warning() -> None:
    dataset = _derive().dataset
    bundle = DatasetBundleBuilder().build(
        (dataset,),
        data_qa=(
            DataQARecord(
                rule_id="qa_passed_internal",
                severity="INFO",
                passed=True,
                message="internal pass detail",
                dataset_id=dataset.dataset_id,
            ),
            DataQARecord(
                rule_id="qa_material_warning",
                severity="WARNING",
                passed=False,
                message="low sample affects interpretation",
                dataset_id=dataset.dataset_id,
            ),
        ),
    )
    package, analysis, _, _, plan, _ = await _plans("查询2026年7月各Channel失败率")
    query = DslCompiler(fields=package.fields(), metrics=package.metrics()).compile(
        plan, plan.steps[0].step_id
    )
    evidence = EvidenceBuilder().build(
        analysis_plan=analysis,
        query_plan=plan,
        compiled_queries=(query,),
        executions=(),
        bundle=bundle,
        metric_definitions=package.metrics(),
        semantic_package_version=package.manifest.package_version,
    )

    assert evidence.business.quality == ()
    assert evidence.business.quality_summary is not None
    assert evidence.business.quality_summary.status == "WARNING"
    assert evidence.business.quality_summary.material_warnings == (
        "low sample affects interpretation",
    )
    assert "internal pass detail" not in evidence.business.model_dump_json()


def test_artifact_store_hash_size_and_tamper_checks(tmp_path: Path) -> None:
    store = EvidenceArtifactStore(tmp_path, maximum_bytes=256)
    artifact_id, digest, byte_size = store.write_json({"aggregations": {"x": 1}})
    content = store.read_json(artifact_id, expected_hash=digest)
    assert len(content) == byte_size
    assert b'"aggregations"' in content

    with pytest.raises(EvidenceArtifactError, match="configured limit"):
        store.write_json({"large": "x" * 300})
    with pytest.raises(EvidenceArtifactError, match="hash mismatch"):
        store.read_json(artifact_id, expected_hash="sha256:" + "0" * 64)


def test_source_table_artifact_hashes_the_exact_downloadable_csv() -> None:
    dataset = _derive().dataset
    artifact = EvidenceBuilder._dataset_artifact(dataset, "source_result_table")
    csv_bytes = EvidenceExporter().dataset_csv(dataset).encode("utf-8")

    assert artifact.byte_size == len(csv_bytes)
    assert artifact.content_hash == f"sha256:{hashlib.sha256(csv_bytes).hexdigest()}"
    assert artifact.row_count == len(dataset.rows)
    assert artifact.source_ids[0] == dataset.object_id
