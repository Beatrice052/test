from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from app.agent.contracts import AnalysisPlan
from app.semantic.models import CompiledSemanticModel, FieldAccess
from app.semantic.retriever import SemanticRetriever


class AnswerabilityStatus(StrEnum):
    ANSWERABLE = "ANSWERABLE"
    ANSWERABLE_WITH_CAVEAT = "ANSWERABLE_WITH_CAVEAT"
    NEEDS_CLARIFICATION = "NEEDS_CLARIFICATION"
    FIELD_NOT_FOUND = "FIELD_NOT_FOUND"
    METRIC_NOT_DEFINED = "METRIC_NOT_DEFINED"
    QUERY_NOT_SUPPORTED = "QUERY_NOT_SUPPORTED"
    POLICY_BLOCKED = "POLICY_BLOCKED"


class ResolutionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: AnswerabilityStatus
    field_resolution: dict[str, str] = Field(default_factory=dict)
    metric_resolution: dict[str, str] = Field(default_factory=dict)
    caveats: list[str] = Field(default_factory=list)
    reason_codes: list[str] = Field(default_factory=list)
    clarification_question: str | None = None
    clarification_slot: str | None = None
    clarification_choices: list[str] = Field(default_factory=list)


class SemanticResolver:
    def __init__(self, model: CompiledSemanticModel) -> None:
        self.model = model
        self.retriever = SemanticRetriever(model)
        self.fields = model.field_map()
        self.metrics = model.metric_map()

    def resolve(self, plan: AnalysisPlan) -> ResolutionResult:
        metric_resolution: dict[str, str] = {}
        field_resolution: dict[str, str] = {"event_time": self.model.dataset.default_time_field}
        caveats: list[str] = []
        reason_codes: list[str] = []

        for metric_concept in plan.metric_concepts:
            metric = self.metrics.get(metric_concept)
            if metric is None:
                return ResolutionResult(
                    status=AnswerabilityStatus.METRIC_NOT_DEFINED,
                    reason_codes=["METRIC_NOT_DEFINED"],
                )
            metric_resolution[metric_concept] = metric.version
            caveats.extend(metric.caveats)
            if metric.status != "BUSINESS_CONFIRMED":
                reason_codes.append("POC_METRIC")
            if metric.lifecycle_field:
                field_resolution["lifecycle_status"] = metric.lifecycle_field

        for concept in plan.dimension_concepts:
            if concept == "date":
                field_resolution["date"] = self.model.dataset.default_time_field
                continue
            if concept == "ambiguous_status":
                return ResolutionResult(
                    status=AnswerabilityStatus.NEEDS_CLARIFICATION,
                    clarification_question=(
                        "你希望查看生命周期状态 status，还是运营商原始回执码 statusCode？"
                    ),
                    clarification_slot="status_field",
                    clarification_choices=["status", "statusCode"],
                    reason_codes=["AMBIGUOUS_STATUS_FIELD"],
                )

            field = self.fields.get(concept)
            if field is None:
                candidates = self.retriever.retrieve(concept, required_operation="group_by")
                field = self.fields.get(candidates[0].field_path) if candidates else None
            if field is None:
                return ResolutionResult(
                    status=AnswerabilityStatus.FIELD_NOT_FOUND,
                    reason_codes=["FIELD_NOT_FOUND"],
                )
            if field.access is FieldAccess.BLOCKED:
                return ResolutionResult(
                    status=AnswerabilityStatus.POLICY_BLOCKED,
                    reason_codes=["POLICY_BLOCKED"],
                )
            if field.access is FieldAccess.REVIEW_REQUIRED:
                return ResolutionResult(
                    status=AnswerabilityStatus.QUERY_NOT_SUPPORTED,
                    reason_codes=["FIELD_REVIEW_REQUIRED"],
                )
            if concept != "date" and "group_by" not in field.allowed_operations:
                return ResolutionResult(
                    status=AnswerabilityStatus.QUERY_NOT_SUPPORTED,
                    reason_codes=["OPERATION_NOT_ALLOWED"],
                )
            field_resolution[concept] = field.physical_aggregation_path or field.field_path

        for filter_concept in plan.filter_concepts:
            field = self.fields.get(filter_concept.concept)
            if field is None:
                return ResolutionResult(
                    status=AnswerabilityStatus.FIELD_NOT_FOUND,
                    reason_codes=["FILTER_FIELD_NOT_FOUND"],
                )
            if field.access is FieldAccess.BLOCKED:
                return ResolutionResult(
                    status=AnswerabilityStatus.POLICY_BLOCKED,
                    reason_codes=["POLICY_BLOCKED"],
                )
            field_resolution[f"filter:{filter_concept.concept}"] = field.field_path

        status = (
            AnswerabilityStatus.ANSWERABLE_WITH_CAVEAT
            if caveats or reason_codes
            else AnswerabilityStatus.ANSWERABLE
        )
        return ResolutionResult(
            status=status,
            field_resolution=field_resolution,
            metric_resolution=metric_resolution,
            caveats=list(dict.fromkeys(caveats)),
            reason_codes=list(dict.fromkeys(reason_codes)),
        )
