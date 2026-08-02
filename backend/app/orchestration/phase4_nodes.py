"""Gateway execution, dependent binding, normalization, analytics, and QA nodes."""

from dataclasses import dataclass

from app.analytics.bundle import DatasetBundleBuilder
from app.analytics.composite import CompositeResultMerger
from app.analytics.pipeline import AnalyticsPipeline
from app.contracts.common import JsonValue
from app.contracts.dataset import DataQARecord, ReconciliationRecord, TabularDataset
from app.contracts.error import ErrorDetail, StructuredError
from app.contracts.execution import ExecutionRecord, RawSearchResult
from app.contracts.insight import FeatureSummary
from app.contracts.query import CompiledQuery, QueryPlan, QueryStep
from app.gateway.executor import GatewayExecutor
from app.orchestration.state import ChatBIState
from app.persistence.session_repository import SessionRepository
from app.query.builder import DependentQueryBinder
from app.query.compiler import DslCompiler
from app.query.validator import CompiledQueryValidator


class Phase4Nodes:
    def __init__(
        self,
        *,
        sessions: SessionRepository,
        executor: GatewayExecutor,
        compiler: DslCompiler,
        validator: CompiledQueryValidator,
        analytics: AnalyticsPipeline,
        semantic_package_version: str,
        max_composite_pages: int = 20,
        max_raw_response_bytes: int = 10_000_000,
    ) -> None:
        self.sessions = sessions
        self.executor = executor
        self.compiler = compiler
        self.validator = validator
        self.analytics = analytics
        self.semantic_package_version = semantic_package_version
        self.max_composite_pages = max_composite_pages
        self.max_raw_response_bytes = max_raw_response_bytes
        self.binder = DependentQueryBinder()
        self.bundle_builder = DatasetBundleBuilder()
        self.composite_merger = CompositeResultMerger()

    async def execute_and_analyze(self, state: ChatBIState) -> dict[str, object]:
        plan = state["query_plan"]
        compiled_by_step = {item.step_id: item for item in state["compiled_queries"]}
        raw_by_step: dict[str, RawSearchResult] = {}
        executions: list[ExecutionRecord] = []
        raw_results: list[RawSearchResult] = []
        datasets: list[TabularDataset] = []
        qa_records: list[DataQARecord] = []
        reconciliations: list[ReconciliationRecord] = []
        feature_summaries: list[FeatureSummary] = []
        for step in plan.steps:
            query = compiled_by_step.get(step.step_id)
            if query is None:
                query = self._compile_dependent(step, plan, compiled_by_step, raw_by_step)
                compiled_by_step[step.step_id] = query
            execution = await self.executor.execute(query)
            executions.append(execution.record)
            step_executions = [execution.record]
            result = execution.result
            failure_record = execution.record
            if result is not None:
                completion = await self._complete_composite(query, result)
                executions.extend(completion.execution_records)
                step_executions.extend(completion.execution_records)
                result = completion.result
                if completion.execution_records:
                    failure_record = completion.execution_records[-1]
                if completion.error_code is not None:
                    if not step.required:
                        qa_records.append(self._optional_failure(step, completion.error_code))
                        continue
                    return self._gateway_failure(
                        state,
                        compiled_by_step,
                        executions,
                        raw_results,
                        step,
                        failure_record,
                        completion.error_code,
                        completion.retryable,
                    )
            if result is None:
                if not step.required:
                    qa_records.append(
                        self._optional_failure(step, failure_record.error_code or "GW_FAILED")
                    )
                    continue
                return self._gateway_failure(
                    state,
                    compiled_by_step,
                    executions,
                    raw_results,
                    step,
                    failure_record,
                    failure_record.error_code or "GW_EXECUTION_FAILED",
                    failure_record.retryable,
                )
            raw_by_step[step.step_id] = result
            raw_results.append(result)
            analyzed = self.analytics.process(
                query,
                result,
                tuple(step_executions),
                method_ids=state["resolved_analysis"].method_ids,
            )
            datasets.extend(analyzed.bundle.datasets)
            qa_records.extend(analyzed.bundle.data_qa)
            reconciliations.extend(analyzed.bundle.reconciliation)
            feature_summaries.extend(analyzed.feature_summaries)
            if analyzed.fatal:
                bundle = self.bundle_builder.build(
                    tuple(datasets),
                    data_qa=tuple(qa_records),
                    reconciliation=tuple(reconciliations),
                )
                return {
                    "compiled_queries": tuple(compiled_by_step.values()),
                    "execution_records": tuple(executions),
                    "raw_results": tuple(raw_results),
                    "dataset_bundle": bundle,
                    "feature_summaries": (),
                    "phase4_route": "qa_failed",
                }
        if not datasets:
            error = StructuredError(
                code="GW_ALL_QUERY_STEPS_FAILED",
                message="No query step produced a usable Dataset.",
                correlation_id=state["correlation_id"],
                retryable=False,
                suggested_action="Retry or simplify the requested analysis.",
            )
            return {
                "compiled_queries": tuple(compiled_by_step.values()),
                "execution_records": tuple(executions),
                "raw_results": tuple(raw_results),
                "phase4_route": "failed",
                "errors": (error,),
            }
        bundle = self.bundle_builder.build(
            tuple(datasets),
            data_qa=tuple(qa_records),
            reconciliation=tuple(reconciliations),
        )
        self.sessions.save_safe_state(
            state["identity"].subject_id,
            state["turn_id"],
            {
                "node": "execute_and_analyze",
                "semantic_package_version": self.semantic_package_version,
                "analysis_plan_id": state["analysis_plan"].object_id,
                "candidate_ids": [bundle.object_id],
            },
        )
        return {
            "compiled_queries": tuple(compiled_by_step.values()),
            "execution_records": tuple(executions),
            "raw_results": tuple(raw_results),
            "dataset_bundle": bundle,
            "feature_summaries": tuple(feature_summaries),
            "phase4_route": "ready",
        }

    async def _complete_composite(
        self,
        query: CompiledQuery,
        first_page: RawSearchResult,
    ) -> "_CompositeCompletion":
        after_key = self._composite_after_key(first_page)
        if after_key is None:
            return _CompositeCompletion(result=first_page)
        pages = [first_page]
        records: list[ExecutionRecord] = []
        while after_key is not None and len(pages) < self.max_composite_pages:
            page_query = self.compiler.compile_composite_page(query, after_key=after_key)
            execution = await self.executor.execute(page_query)
            records.append(execution.record)
            if execution.result is None:
                return _CompositeCompletion(
                    result=None,
                    execution_records=tuple(records),
                    error_code=execution.record.error_code or "GW_COMPOSITE_PAGE_FAILED",
                    retryable=execution.record.retryable,
                )
            pages.append(execution.result)
            if sum(item.raw_size_bytes for item in pages) > self.max_raw_response_bytes:
                return _CompositeCompletion(
                    result=None,
                    execution_records=tuple(records),
                    error_code="GW_COMPOSITE_RESPONSE_TOO_LARGE",
                )
            after_key = self._composite_after_key(execution.result)
        if after_key is not None:
            return _CompositeCompletion(
                result=None,
                execution_records=tuple(records),
                error_code="GW_COMPOSITE_PAGE_LIMIT",
            )
        return _CompositeCompletion(
            result=self.composite_merger.merge(tuple(pages)),
            execution_records=tuple(records),
        )

    @staticmethod
    def _composite_after_key(result: RawSearchResult) -> dict[str, JsonValue] | None:
        candidates = [
            value.get("after_key")
            for value in result.aggregations.values()
            if isinstance(value, dict) and value.get("after_key") is not None
        ]
        if not candidates:
            return None
        if len(candidates) != 1 or not isinstance(candidates[0], dict):
            raise ValueError("composite response has an invalid after_key")
        return candidates[0]

    @staticmethod
    def _optional_failure(step: QueryStep, error_code: str) -> DataQARecord:
        return DataQARecord(
            rule_id="qa_optional_query_failed",
            severity="ERROR",
            passed=False,
            message=(
                f"optional query step {step.step_id} failed; "
                "the remaining validated analysis is still available"
            ),
            dataset_id=None,
            details={"error_code": error_code},
        )

    @staticmethod
    def _gateway_failure(
        state: ChatBIState,
        compiled_by_step: dict[str, CompiledQuery],
        executions: list[ExecutionRecord],
        raw_results: list[RawSearchResult],
        step: QueryStep,
        record: ExecutionRecord,
        error_code: str,
        retryable: bool,
    ) -> dict[str, object]:
        error = StructuredError(
            code=error_code,
            message="OpenSearch query execution failed.",
            correlation_id=state["correlation_id"],
            retryable=retryable,
            details=(
                ErrorDetail(
                    code="QUERY_STEP_FAILED",
                    message=f"step {step.step_id} failed after {record.attempt} attempts",
                ),
            ),
            suggested_action="Retry if the failure is marked retryable.",
        )
        return {
            "compiled_queries": tuple(compiled_by_step.values()),
            "execution_records": tuple(executions),
            "raw_results": tuple(raw_results),
            "phase4_route": "failed",
            "errors": (error,),
        }

    def _compile_dependent(
        self,
        step: QueryStep,
        plan: QueryPlan,
        compiled_by_step: dict[str, CompiledQuery],
        raw_by_step: dict[str, RawSearchResult],
    ) -> CompiledQuery:
        values_by_parameter = {}
        for binding in step.parameter_bindings:
            source_step = next(
                (
                    item
                    for item in plan.steps
                    if item.result_contract_id == binding.source_dataset_contract
                    and item.step_id in step.depends_on
                ),
                None,
            )
            if source_step is None:
                raise ValueError("dependent binding has no declared source step")
            source_query = compiled_by_step.get(source_step.step_id)
            source_result = raw_by_step.get(source_step.step_id)
            if source_query is None or source_result is None:
                raise ValueError("dependent source has not completed")
            values_by_parameter[binding.parameter] = self.binder.values_from_result(
                binding, source_query, source_result
            )
        bound_step = self.binder.bind(step, values_by_parameter)
        bound_plan = plan.model_copy(
            update={
                "steps": tuple(
                    bound_step if item.step_id == step.step_id else item for item in plan.steps
                )
            }
        )
        query = self.compiler.compile(bound_plan, step.step_id)
        self.validator.validate(query, bound_plan)
        return query

    @staticmethod
    def phase4_ready(state: ChatBIState) -> dict[str, object]:
        if not state.get("dataset_bundle") or not state.get("feature_summaries"):
            raise ValueError("phase4 ready requires a bundle and feature summary")
        return {"terminal_status": "DATASET_READY"}

    @staticmethod
    def phase4_qa_failed(state: ChatBIState) -> dict[str, object]:
        if not state.get("dataset_bundle"):
            raise ValueError("QA failure requires an auditable DatasetBundle")
        return {"terminal_status": "DATA_QA_FAILED"}

    @staticmethod
    def phase4_gateway_failed(state: ChatBIState) -> dict[str, object]:
        if not state.get("errors"):
            raise ValueError("Gateway failure requires a StructuredError")
        return {"terminal_status": "GATEWAY_FAILED"}


@dataclass(frozen=True, slots=True)
class _CompositeCompletion:
    result: RawSearchResult | None
    execution_records: tuple[ExecutionRecord, ...] = ()
    error_code: str | None = None
    retryable: bool = False
