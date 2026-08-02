"""Build a bounded deterministic feature view; never pass full large tables to Agent C."""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime

from app.analytics.qa import DataQAEngine
from app.contracts.common import JsonValue, Provenance, semantic_hash
from app.contracts.dataset import DataQARecord, DatasetRow, TabularDataset
from app.contracts.insight import FeatureSummary, StatisticalResult
from app.persistence.ids import new_id


class FeatureSummaryBlocked(ValueError):
    pass


class FeatureSummaryBuilder:
    def build(
        self,
        dataset: TabularDataset,
        *,
        statistical_results: tuple[StatisticalResult, ...] = (),
        qa_records: tuple[DataQARecord, ...] = (),
        max_rows: int = 5,
    ) -> FeatureSummary:
        relevant_qa = tuple(
            item for item in qa_records if item.dataset_id in {None, dataset.dataset_id}
        )
        if DataQAEngine.has_fatal(relevant_qa):
            raise FeatureSummaryBlocked("FATAL data QA prevents insight generation")
        numeric_columns = [
            item.name
            for item in dataset.columns
            if item.data_type in {"integer", "number", "metric"}
            and item.semantic_role != "metadata"
        ]
        totals: dict[str, JsonValue] = {}
        ranges: dict[str, JsonValue] = {}
        for column in numeric_columns:
            numeric_values: list[float] = []
            for row in dataset.rows:
                raw_value = row.values.get(column)
                if isinstance(raw_value, int | float) and not isinstance(raw_value, bool):
                    numeric_values.append(float(raw_value))
            if numeric_values:
                totals[column] = round(sum(numeric_values), 12)
                ranges[column] = {"min": min(numeric_values), "max": max(numeric_values)}
        sort_column = numeric_columns[0] if numeric_columns else None
        ranked = list(dataset.rows)
        if sort_column is not None:
            ranked.sort(key=lambda row: self._sort_key(row, sort_column))
        top_rows = tuple(self._feature_row(item) for item in ranked[:max_rows])
        bottom_rows = tuple(self._feature_row(item) for item in reversed(ranked[-max_rows:]))
        time_columns = [item.name for item in dataset.columns if item.data_type == "datetime"]
        time_features: dict[str, JsonValue] = {}
        for column in time_columns:
            time_values = sorted(
                str(value) for row in dataset.rows if (value := row.values.get(column)) is not None
            )
            if time_values:
                time_features[column] = {"from": time_values[0], "to": time_values[-1]}
        qa_summary: dict[str, int] = dict(
            Counter(str(item.severity) for item in relevant_qa if not item.passed)
        )
        payload = {
            "dataset_id": dataset.dataset_id,
            "row_count": len(dataset.rows),
            "columns": [item.name for item in dataset.columns],
            "top_rows": top_rows,
            "bottom_rows": bottom_rows,
            "totals": totals,
            "ranges": ranges,
            "time_features": time_features,
            "statistical_results": [item.model_dump(mode="json") for item in statistical_results],
            "qa_summary": qa_summary,
            "sample_rows": [self._feature_row(item) for item in dataset.rows[:max_rows]],
        }
        return FeatureSummary(
            object_id=new_id("fs"),
            created_at=datetime.now(UTC),
            content_hash=semantic_hash(payload),
            provenance=Provenance(
                producer="analytics.feature_summary_builder",
                source_ids=(dataset.object_id,),
            ),
            dataset_id=dataset.dataset_id,
            row_count=len(dataset.rows),
            columns=tuple(item.name for item in dataset.columns),
            top_rows=top_rows,
            bottom_rows=bottom_rows,
            totals=totals,
            ranges=ranges,
            time_features=time_features,
            statistical_results=statistical_results,
            qa_summary=qa_summary,
            sample_rows=tuple(self._feature_row(item) for item in dataset.rows[:max_rows]),
        )

    @staticmethod
    def _feature_row(row: DatasetRow) -> dict[str, JsonValue]:
        return {"row_id": row.row_id, **row.values}

    @staticmethod
    def _sort_key(row: DatasetRow, column: str) -> tuple[float, str]:
        value = row.values.get(column)
        score = (
            -float(value)
            if isinstance(value, int | float) and not isinstance(value, bool)
            else float("inf")
        )
        return score, row.row_id
