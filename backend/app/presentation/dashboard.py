"""Validate visualization intent and build only the safe DashboardSpec subset."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal

from app.contracts.common import Provenance, semantic_hash
from app.contracts.dashboard import (
    ChartEncoding,
    DashboardBlock,
    DashboardSpec,
    KpiItem,
    VisualizationCandidate,
    VisualizationDefinition,
)
from app.contracts.dataset import DatasetBundle, DatasetColumn, TabularDataset
from app.contracts.insight import ClaimSpec
from app.contracts.metric import MetricDefinition, MetricLevel
from app.persistence.ids import new_id


class FeasibilityDecision(StrEnum):
    ACCEPT = "ACCEPT"
    ACCEPT_WITH_TRANSFORM = "ACCEPT_WITH_TRANSFORM"
    DOWNGRADE_TO_TABLE = "DOWNGRADE_TO_TABLE"
    REJECT = "REJECT"


@dataclass(frozen=True, slots=True)
class FeasibilityResult:
    candidate: VisualizationCandidate
    decision: FeasibilityDecision
    chart_type: str | None = None
    encoding: ChartEncoding | None = None
    transforms: tuple[str, ...] = ()
    reason: str = ""


class ChartFeasibilityValidator:
    def __init__(self, definitions: tuple[VisualizationDefinition, ...]) -> None:
        self.definitions = {item.intent: item for item in definitions}

    def validate(
        self,
        candidate: VisualizationCandidate,
        bundle: DatasetBundle,
    ) -> FeasibilityResult:
        dataset = next(
            (item for item in bundle.datasets if item.dataset_id == candidate.dataset_id),
            None,
        )
        definition = self.definitions.get(candidate.intent)
        if dataset is None or definition is None:
            return FeasibilityResult(
                candidate, FeasibilityDecision.REJECT, reason="dataset or intent is unavailable"
            )
        if any(
            item.dataset_id == dataset.dataset_id
            and item.severity in {"ERROR", "FATAL"}
            and not item.passed
            for item in bundle.data_qa
        ):
            return FeasibilityResult(
                candidate, FeasibilityDecision.REJECT, reason="dataset is blocked by QA"
            )
        chart_type = next(
            (
                item
                for item in candidate.preferred_chart_types
                if item in definition.allowed_chart_types
            ),
            None,
        )
        if chart_type is None:
            return FeasibilityResult(
                candidate,
                FeasibilityDecision.DOWNGRADE_TO_TABLE,
                reason="preferred chart type is not allowlisted",
            )
        if len(dataset.rows) < definition.minimum_rows:
            return FeasibilityResult(
                candidate,
                FeasibilityDecision.DOWNGRADE_TO_TABLE,
                reason="dataset has too few rows",
            )
        if definition.requires_complete_distribution and not dataset.complete:
            return FeasibilityResult(
                candidate,
                FeasibilityDecision.REJECT,
                reason="chart requires a complete distribution",
            )
        try:
            dimension = self._role_column(
                dataset,
                candidate.dimension_roles,
                preferred_roles=("time", "category"),
            )
            series = self._role_column(
                dataset,
                candidate.dimension_roles,
                preferred_roles=("series",),
                required=False,
            )
            measure = self._role_column(dataset, candidate.measure_roles)
        except ValueError as error:
            return FeasibilityResult(
                candidate, FeasibilityDecision.DOWNGRADE_TO_TABLE, reason=str(error)
            )
        if measure is None:
            return FeasibilityResult(
                candidate,
                FeasibilityDecision.DOWNGRADE_TO_TABLE,
                reason="chart has no measure binding",
            )
        if not self._has_variance(dataset, measure.name):
            return FeasibilityResult(
                candidate,
                FeasibilityDecision.REJECT,
                reason="measure has no meaningful variation",
            )
        if candidate.intent in {"time_trend", "anomaly"}:
            if dimension is None or not (
                dimension.data_type == "datetime" or dimension.semantic_type == "time_dimension"
            ):
                return FeasibilityResult(
                    candidate,
                    FeasibilityDecision.DOWNGRADE_TO_TABLE,
                    reason="time trend requires a datetime dimension",
                )
            time_points = {
                row.values.get(dimension.name)
                for row in dataset.rows
                if row.values.get(dimension.name) is not None
            }
            if len(time_points) < definition.minimum_time_points:
                return FeasibilityResult(
                    candidate,
                    FeasibilityDecision.DOWNGRADE_TO_TABLE,
                    reason="time trend has too few points",
                )
        if chart_type in {"stacked_bar", "heatmap"} and series is None:
            return FeasibilityResult(
                candidate,
                FeasibilityDecision.DOWNGRADE_TO_TABLE,
                reason=f"{chart_type} requires a validated series dimension",
            )
        if chart_type == "donut" and series is not None:
            return FeasibilityResult(
                candidate,
                FeasibilityDecision.DOWNGRADE_TO_TABLE,
                reason="donut requires one categorical dimension at a reconciled grain",
            )
        if candidate.intent == "composition" and dimension is not None:
            categories = {
                row.values.get(dimension.name)
                for row in dataset.rows
                if row.values.get(dimension.name) is not None
            }
            if len(categories) < 2:
                return FeasibilityResult(
                    candidate,
                    FeasibilityDecision.DOWNGRADE_TO_TABLE,
                    reason="composition requires at least two populated categories",
                )
        encoded_dimensions = tuple(
            dict.fromkeys(item.name for item in (dimension, series) if item is not None)
        )
        if set(dataset.grain) != set(encoded_dimensions):
            return FeasibilityResult(
                candidate,
                FeasibilityDecision.DOWNGRADE_TO_TABLE,
                reason=(
                    "chart encoding does not represent the complete Dataset grain: "
                    f"grain={dataset.grain}, encoded={encoded_dimensions}"
                ),
            )
        encoded_keys = [
            semantic_hash([row.values.get(item) for item in encoded_dimensions])
            for row in dataset.rows
        ]
        if len(encoded_keys) != len(set(encoded_keys)):
            return FeasibilityResult(
                candidate,
                FeasibilityDecision.DOWNGRADE_TO_TABLE,
                reason="chart Dataset has duplicate rows at the declared encoding grain",
            )
        encoding = ChartEncoding(
            x=dimension.name if dimension is not None else None,
            y=measure.name,
            category=dimension.name if dimension is not None else None,
            value=measure.name,
            color=series.name if series is not None else None,
            series=series.name if series is not None else None,
            tooltip_fields=(
                *(item.name for item in (dimension, series, measure) if item is not None),
                "metric_metadata",
            ),
        )
        if len(dataset.rows) > definition.maximum_categories:
            if not dataset.complete:
                return FeasibilityResult(
                    candidate,
                    FeasibilityDecision.REJECT,
                    reason="incomplete high-cardinality chart would be misleading",
                )
            return FeasibilityResult(
                candidate,
                FeasibilityDecision.DOWNGRADE_TO_TABLE,
                reason=(
                    "category count exceeds the governed chart limit; use the complete "
                    "auditable table instead of silently applying an unverified Top-N rollup"
                ),
            )
        return FeasibilityResult(
            candidate,
            FeasibilityDecision.ACCEPT,
            chart_type=chart_type,
            encoding=encoding,
            transforms=("stable_color_assignment",),
            reason="candidate is feasible",
        )

    @classmethod
    def _role_column(
        cls,
        dataset: TabularDataset,
        roles: dict[str, str],
        *,
        preferred_roles: tuple[str, ...] = (),
        required: bool = True,
    ) -> DatasetColumn | None:
        if not roles:
            return None
        requested = next(
            (roles[item] for item in preferred_roles if item in roles),
            next(iter(roles.values())) if required else None,
        )
        if requested is None:
            return None
        exact = [item for item in dataset.columns if item.name == requested]
        if len(exact) == 1:
            return exact[0]
        leaf = [item for item in dataset.columns if item.name.rsplit(".", 1)[-1] == requested]
        if len(leaf) == 1:
            return leaf[0]
        raise ValueError(f"visualization column is missing or ambiguous: {requested}")

    @staticmethod
    def _has_variance(dataset: TabularDataset, column: str) -> bool:
        values = {
            value
            for row in dataset.rows
            if isinstance((value := row.values.get(column)), int | float)
            and not isinstance(value, bool)
        }
        return len(values) > 1


class DashboardBuilder:
    def __init__(
        self,
        validator: ChartFeasibilityValidator,
        metric_definitions: tuple[MetricDefinition, ...] = (),
    ) -> None:
        self.validator = validator
        self.metric_definitions = {item.versioned_id: item for item in metric_definitions}

    def build(
        self,
        *,
        title: str,
        answer_summary: str,
        candidates: tuple[VisualizationCandidate, ...],
        claims: tuple[ClaimSpec, ...],
        bundle: DatasetBundle,
        max_blocks: int,
        kpi_metric_ids: tuple[str, ...] = (),
        limitations: tuple[str, ...] = (),
        follow_up_suggestions: tuple[str, ...] = (),
    ) -> DashboardSpec:
        blocks: list[DashboardBlock] = [
            DashboardBlock(
                block_id="block_answer_summary",
                type="answer_summary",
                title="总分析",
                description="回答中的数字均来自已验证 Dataset, 并可在证据面板定位。",
                evidence_refs=tuple(item.object_id for item in claims),
                content={"text": answer_summary},
                insights=self._insights_not_in_summary(answer_summary, claims),
            )
        ]
        kpis = self._kpis(bundle, kpi_metric_ids)
        if kpis:
            blocks.append(
                DashboardBlock(
                    block_id="block_kpi_overview",
                    type="kpi_group",
                    title="核心指标总览",
                    kpis=kpis,
                    evidence_refs=tuple(
                        dict.fromkeys(row_id for item in kpis for row_id in item.evidence_row_ids)
                    ),
                )
            )
        seen: set[tuple[str, str, str]] = set()
        # A business table must come from a real visualization candidate. Technical
        # aggregation detail is always exposed through the Evidence package instead.
        table_candidates: dict[str, tuple[VisualizationCandidate, str]] = {}
        for candidate in candidates:
            result = self.validator.validate(candidate, bundle)
            if result.decision == FeasibilityDecision.REJECT:
                continue
            if result.decision == FeasibilityDecision.DOWNGRADE_TO_TABLE:
                table_candidates.setdefault(candidate.dataset_id, (candidate, result.reason))
                continue
            if result.chart_type is None or result.encoding is None:
                continue
            dataset = next(
                item for item in bundle.datasets if item.dataset_id == candidate.dataset_id
            )
            key = (candidate.dataset_id, candidate.intent, result.chart_type)
            if key in seen:
                continue
            seen.add(key)
            blocks.append(
                DashboardBlock.model_validate(
                    {
                        "block_id": f"block_chart_{candidate.candidate_id}",
                        "type": "chart",
                        "title": candidate.analytical_question,
                        "description": candidate.reason,
                        # Public Dashboard references are immutable Dataset object IDs.  The
                        # logical dataset_id is intentionally reusable inside one analysis
                        # plan and therefore cannot safely address historical answers.
                        "dataset_id": dataset.object_id,
                        "visualization_intent": candidate.intent,
                        "chart_type": result.chart_type,
                        "encoding": result.encoding.model_dump(mode="json"),
                        "sort": (f"-{result.encoding.value}",) if result.encoding.value else (),
                        "axis_format": {
                            "value": self._axis_format(
                                bundle, candidate.dataset_id, result.encoding
                            )
                        },
                        "stack": result.chart_type == "stacked_bar",
                        "legend": result.encoding.series is not None,
                        "evidence_refs": tuple(row.row_id for row in dataset.rows[:100]),
                        "content": {
                            "transform": ",".join(result.transforms),
                            "top_n": 20,
                            "pareto_points": self._pareto_points(
                                dataset,
                                result.encoding,
                            )
                            if result.chart_type == "pareto"
                            else [],
                        },
                    },
                    strict=False,
                )
            )
        for dataset_id, (candidate, downgrade_reason) in table_candidates.items():
            dataset = next(item for item in bundle.datasets if item.dataset_id == dataset_id)
            requested_type = next(iter(candidate.preferred_chart_types), "table")
            table_type: Literal["pivot_table", "data_table"] = (
                "pivot_table" if requested_type == "pivot" else "data_table"
            )
            blocks.append(
                DashboardBlock(
                    block_id=f"block_table_{candidate.candidate_id}",
                    type=table_type,
                    title=candidate.analytical_question,
                    description=(
                        "按本次问题选择的维度与指标展示业务结果。"
                        "完整检索结果、指标计算与 DSL 请在查看证据中核查。"
                    ),
                    dataset_id=dataset.object_id,
                    chart_type="pivot" if table_type == "pivot_table" else "table",
                    evidence_refs=tuple(item.row_id for item in dataset.rows[:100]),
                    content={"presentation_reason": downgrade_reason},
                )
            )
        if limitations:
            blocks.append(
                DashboardBlock(
                    block_id="block_analysis_boundaries",
                    type="context_summary",
                    title="分析边界",
                    insights=limitations,
                    content={"text": "; ".join(limitations)},
                )
            )
        if follow_up_suggestions:
            blocks.append(
                DashboardBlock(
                    block_id="block_follow_up_suggestions",
                    type="follow_up_suggestions",
                    title="推荐追问",
                    suggestions=follow_up_suggestions,
                )
            )
        if all(not item.rows for item in bundle.datasets):
            blocks = [
                blocks[0],
                DashboardBlock(
                    block_id="block_empty_state",
                    type="empty_state",
                    title="没有匹配数据",
                    content={"text": "所选时间与过滤范围内没有匹配的聚合记录。"},
                ),
            ]
        blocks = blocks[:max_blocks]
        payload = {
            "title": title,
            "layout": "auto_grid",
            "blocks": [item.model_dump(mode="json") for item in blocks],
            "warnings": bundle.warnings,
        }
        return DashboardSpec(
            object_id=new_id("dsh"),
            created_at=datetime.now(UTC),
            content_hash=semantic_hash(payload),
            provenance=Provenance(
                producer="presentation.dashboard_builder",
                source_ids=tuple(item.object_id for item in bundle.datasets),
            ),
            title=title,
            blocks=tuple(blocks),
            warnings=bundle.warnings,
        )

    @classmethod
    def _insights_not_in_summary(
        cls,
        answer_summary: str,
        claims: tuple[ClaimSpec, ...],
    ) -> tuple[str, ...]:
        summary = cls._normalize_narrative(answer_summary)
        results: list[str] = []
        seen: set[str] = set()
        for claim in claims:
            normalized = cls._normalize_narrative(claim.text)
            if not normalized or normalized in summary or normalized in seen:
                continue
            seen.add(normalized)
            results.append(claim.text)
        return tuple(results)

    @staticmethod
    def _normalize_narrative(value: str) -> str:
        return "".join(character.casefold() for character in value if character.isalnum())

    def _kpis(
        self,
        bundle: DatasetBundle,
        selected_metric_ids: tuple[str, ...],
    ) -> tuple[KpiItem, ...]:
        requested = tuple(dict.fromkeys(selected_metric_ids))
        if not requested:
            return ()
        overall = next(
            (
                item
                for item in bundle.datasets
                if item.kind == "derived" and not item.grain and len(item.rows) == 1
            ),
            None,
        )
        if overall is None:
            return ()
        row = overall.rows[0]
        result: list[KpiItem] = []
        metadata = row.values.get("metric_metadata")
        metadata_items = metadata if isinstance(metadata, dict) else {}
        metric_columns = tuple(item for item in overall.columns if item.semantic_role == "metric")
        seen_columns: set[str] = set()
        for requested_id in requested:
            column = next(
                (
                    item
                    for item in metric_columns
                    if requested_id in {item.name, item.metric_id}
                    or (
                        (candidate_definition := self.metric_definitions.get(item.name)) is not None
                        and requested_id
                        in {
                            candidate_definition.metric_id,
                            candidate_definition.versioned_id,
                        }
                    )
                ),
                None,
            )
            if column is None or column.name in seen_columns:
                continue
            seen_columns.add(column.name)
            value = row.values.get(column.name)
            if not isinstance(value, int | float) or isinstance(value, bool):
                continue
            definition = self.metric_definitions.get(column.name)
            # Never promote an unregistered calculation into the core KPI row.
            if definition is None:
                continue
            label = definition.display_name
            metric_metadata = (
                metadata_items.get(column.metric_id) if column.metric_id is not None else None
            )
            quality_value = (
                metric_metadata.get("quality") if isinstance(metric_metadata, dict) else None
            )
            quality: Literal["valid", "insufficient_sample", "not_applicable"] = (
                "insufficient_sample"
                if quality_value == "INSUFFICIENT_SAMPLE"
                else "not_applicable"
                if quality_value in {"INVALID", "NOT_APPLICABLE"}
                else "valid"
            )
            semantic_level = self._semantic_level(definition)
            result.append(
                KpiItem(
                    kpi_id=f"metric_{column.metric_id or column.name}",
                    label=label,
                    value=value,
                    formatted_value=self._format_metric(value, column.unit),
                    unit=self._display_unit(column.unit),
                    semantic_level=semantic_level,
                    quality=quality,
                    definition=definition.business_definition,
                    evidence_row_ids=(row.row_id,),
                )
            )
        return tuple(result)

    @staticmethod
    def _semantic_level(
        definition: MetricDefinition | None,
    ) -> Literal["certified", "governed", "operational", "exploratory"]:
        if definition is None:
            return "governed"
        levels: dict[
            MetricLevel,
            Literal["certified", "governed", "operational", "exploratory"],
        ] = {
            MetricLevel.CERTIFIED: "certified",
            MetricLevel.GOVERNED_DERIVED: "governed",
            MetricLevel.EXPLORATORY: "exploratory",
            MetricLevel.UNSUPPORTED: "exploratory",
        }
        return levels[definition.level]

    @staticmethod
    def _format_metric(value: int | float, unit: str | None) -> str:
        if unit == "ratio":
            return f"{float(value) * 100:.2f}%"
        if unit == "count":
            return f"{int(value):,}" if float(value).is_integer() else f"{value:,.2f}"
        if unit == "milliseconds":
            return f"{value:,.2f} ms"
        return f"{value:,.4g}"

    @staticmethod
    def _display_unit(unit: str | None) -> str | None:
        if unit == "ratio":
            return "%"
        if unit == "count":
            return "条"
        if unit == "milliseconds":
            return "ms"
        return unit

    @staticmethod
    def _axis_format(bundle: DatasetBundle, dataset_id: str, encoding: ChartEncoding) -> str:
        dataset = next(item for item in bundle.datasets if item.dataset_id == dataset_id)
        column = next((item for item in dataset.columns if item.name == encoding.value), None)
        return "percent" if column is not None and column.unit == "ratio" else "number"

    @staticmethod
    def _pareto_points(
        dataset: TabularDataset,
        encoding: ChartEncoding,
    ) -> list[dict[str, object]]:
        """Compute the deterministic Pareto transform before the browser boundary."""

        category_column = encoding.category or encoding.x
        value_column = encoding.value or encoding.y
        if category_column is None or value_column is None:
            return []
        rows = sorted(
            (
                (row.row_id, row.values.get(category_column), float(value))
                for row in dataset.rows
                if (value := row.values.get(value_column)) is not None
                and isinstance(value, int | float)
                and not isinstance(value, bool)
                and value >= 0
            ),
            key=lambda item: (-item[2], item[0]),
        )
        total = sum(item[2] for item in rows)
        if total <= 0:
            return []
        running = 0.0
        points: list[dict[str, object]] = []
        for row_id, category, value in rows:
            running += value
            points.append(
                {
                    "row_id": row_id,
                    "category": category,
                    "value": value,
                    "cumulative_percent": round(running / total * 100, 6),
                }
            )
        return points
