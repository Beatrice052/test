"""Bounded visualization-tool Adapter between Agent C's two structured passes."""

from __future__ import annotations

from datetime import UTC, datetime

from app.contracts.analysis import AnalysisPlan
from app.contracts.common import JsonScalar, JsonValue, Provenance, semantic_hash
from app.contracts.dashboard import (
    ChartEncoding,
    VisualizationCandidate,
    VisualizationPreview,
    VisualProfile,
)
from app.contracts.dataset import DatasetBundle, DatasetRow, TabularDataset
from app.persistence.ids import new_id
from app.presentation.dashboard import ChartFeasibilityValidator, FeasibilityDecision


class GovernedVisualizationExplorer:
    """Execute only validated chart contracts; never execute model-authored code."""

    def __init__(self, validator: ChartFeasibilityValidator) -> None:
        self.validator = validator

    def explore(
        self,
        candidates: tuple[VisualizationCandidate, ...],
        bundle: DatasetBundle,
        *,
        analysis_plan: AnalysisPlan | None = None,
    ) -> tuple[VisualizationPreview, ...]:
        candidate_ids = tuple(item.candidate_id for item in candidates)
        if len(set(candidate_ids)) != len(candidate_ids):
            raise ValueError("visualization candidate IDs are not unique")
        previews: list[VisualizationPreview] = []
        task_visualization_intents = (
            None
            if analysis_plan is None
            else {item.task_id: set(item.visualization_intents) for item in analysis_plan.tasks}
        )
        candidate_budget = (
            len(candidates)
            if analysis_plan is None
            else min(len(candidates), analysis_plan.budget.max_blocks)
        )
        for candidate in candidates[:candidate_budget]:
            dataset = next(
                (item for item in bundle.datasets if item.dataset_id == candidate.dataset_id),
                None,
            )
            result = self.validator.validate(
                candidate,
                bundle,
                task_visualization_intents=task_visualization_intents,
            )
            encoding = result.encoding
            profile = self._profile(dataset, candidate, encoding)
            payload = {
                "candidate": candidate.model_dump(mode="json"),
                "decision": result.decision.value,
                "chart_type": result.chart_type,
                "encoding": None if encoding is None else encoding.model_dump(mode="json"),
                "transforms": result.transforms,
                "reason": result.reason,
                "profile": profile.model_dump(mode="json"),
            }
            previews.append(
                VisualizationPreview(
                    object_id=new_id("vpw"),
                    created_at=datetime.now(UTC),
                    content_hash=semantic_hash(payload),
                    provenance=Provenance(
                        producer="presentation.governed_visualization_explorer",
                        source_ids=(() if dataset is None else (dataset.object_id,)),
                    ),
                    candidate_id=candidate.candidate_id,
                    task_ids=candidate.task_ids,
                    analytical_question=candidate.analytical_question,
                    purpose=candidate.reason,
                    dataset_id=candidate.dataset_id,
                    visualization_intent=candidate.intent,
                    decision=result.decision.value,
                    renderer=(
                        "echarts_contract"
                        if result.decision
                        in {FeasibilityDecision.ACCEPT, FeasibilityDecision.ACCEPT_WITH_TRANSFORM}
                        else "table"
                    ),
                    chart_type=result.chart_type,
                    encoding=encoding,
                    transforms=result.transforms,
                    reason=result.reason,
                    profile=profile,
                    evidence_row_ids=(
                        () if dataset is None else tuple(item.row_id for item in dataset.rows[:100])
                    ),
                )
            )
        return tuple(previews)

    @staticmethod
    def _profile(
        dataset: TabularDataset | None,
        candidate: VisualizationCandidate,
        encoding: ChartEncoding | None,
    ) -> VisualProfile:
        if dataset is None:
            return VisualProfile(
                row_count=0,
                category_count=0,
                series_count=0,
                time_point_count=0,
                visible_columns=(),
            )
        visible_columns = tuple(
            dict.fromkeys(
                item
                for item in (
                    *((encoding.model_dump().values()) if encoding is not None else ()),
                    *candidate.dimension_roles.values(),
                    *candidate.measure_roles.values(),
                )
                if isinstance(item, str)
            )
        )
        category = (
            (encoding.category or encoding.x)
            if encoding is not None
            else next(iter(candidate.dimension_roles.values()), None)
        )
        series = (
            (encoding.series or encoding.color)
            if encoding is not None
            else candidate.dimension_roles.get("series")
        )
        time_columns = {
            item.name
            for item in dataset.columns
            if item.data_type == "datetime" or item.semantic_type == "time_dimension"
        }
        time_column = next((item for item in visible_columns if item in time_columns), None)
        value_columns = tuple(
            dict.fromkeys(
                item
                for item in (
                    *((encoding.value, encoding.y) if encoding is not None else ()),
                    *candidate.measure_roles.values(),
                )
                if isinstance(item, str)
            )
        )
        ranges: dict[str, JsonScalar] = {}
        for column in value_columns:
            values = [
                value
                for row in dataset.rows
                if isinstance((value := row.values.get(column)), int | float)
                and not isinstance(value, bool)
            ]
            if values:
                ranges[f"{column}.min"] = min(values)
                ranges[f"{column}.max"] = max(values)
        representative_rows: list[dict[str, JsonValue]] = []
        for row in GovernedVisualizationExplorer._representative_rows(dataset, value_columns):
            representative_rows.append(
                {
                    "row_id": row.row_id,
                    **{column: row.values.get(column) for column in visible_columns},
                }
            )
        return VisualProfile(
            row_count=len(dataset.rows),
            category_count=GovernedVisualizationExplorer._distinct(dataset, category),
            series_count=GovernedVisualizationExplorer._distinct(dataset, series),
            time_point_count=GovernedVisualizationExplorer._distinct(dataset, time_column),
            visible_columns=visible_columns,
            value_range=ranges,
            representative_rows=tuple(representative_rows),
        )

    @staticmethod
    def _representative_rows(
        dataset: TabularDataset,
        value_columns: tuple[str, ...],
        *,
        limit: int = 12,
    ) -> tuple[DatasetRow, ...]:
        """Sample endpoints, extrema, and interior rows from the full validated shape."""

        rows = dataset.rows
        if len(rows) <= limit:
            return tuple(rows)
        selected: list[int] = []

        def add(index: int) -> None:
            if 0 <= index < len(rows) and index not in selected and len(selected) < limit:
                selected.append(index)

        for index in (0, 1, len(rows) - 2, len(rows) - 1):
            add(index)
        for column in value_columns:
            numeric = [
                (index, value)
                for index, row in enumerate(rows)
                if isinstance((value := row.values.get(column)), int | float)
                and not isinstance(value, bool)
            ]
            if numeric:
                add(min(numeric, key=lambda item: (item[1], item[0]))[0])
                add(max(numeric, key=lambda item: (item[1], -item[0]))[0])
        for slot in range(1, limit + 1):
            add(round(slot * (len(rows) - 1) / (limit + 1)))
        return tuple(rows[index] for index in sorted(selected[:limit]))

    @staticmethod
    def _distinct(dataset: TabularDataset, column: str | None) -> int:
        if column is None:
            return 0
        return len({value for row in dataset.rows if (value := row.values.get(column)) is not None})
