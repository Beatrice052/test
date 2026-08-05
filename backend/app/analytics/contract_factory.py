"""Create the authoritative DatasetContract carried by a compiled query."""

from datetime import UTC, datetime

from app.contracts.common import Provenance, safe_identifier, semantic_hash
from app.contracts.dataset import DatasetColumn, DatasetContract
from app.contracts.metric import AggregationKind, AggregationSpec
from app.contracts.query import CompiledQuery
from app.contracts.semantic import CanonicalField


class DatasetContractFactory:
    def __init__(self, fields: tuple[CanonicalField, ...] = ()) -> None:
        self.fields = {item.field_id: item for item in fields}

    def build(
        self,
        query: CompiledQuery,
        *,
        dataset_id: str | None = None,
    ) -> DatasetContract:
        dimensions = tuple(item.dimension_id for item in query.semantics.bucket_path)
        columns = (
            *(
                DatasetColumn(
                    name=item.dimension_id,
                    data_type="datetime" if item.bucket_kind == "date_histogram" else "string",
                    nullable=True,
                    semantic_role="dimension",
                    field_id=item.dimension_id,
                    display_name=(
                        self.fields[item.dimension_id].display_name
                        if item.dimension_id in self.fields
                        else item.dimension_id.rsplit(".", 1)[-1]
                    ),
                    semantic_type=(
                        self.fields[item.dimension_id].semantic_type.value
                        if item.dimension_id in self.fields
                        else None
                    ),
                    business_domain=(
                        self.fields[item.dimension_id].business_domain
                        if item.dimension_id in self.fields
                        else None
                    ),
                    security_classification=(
                        self.fields[item.dimension_id].security.classification
                        if item.dimension_id in self.fields
                        else "internal"
                    ),
                )
                for item in query.semantics.bucket_path
            ),
            DatasetColumn(
                name="record_count",
                data_type="integer",
                nullable=False,
                semantic_role="measure",
                unit="count",
                aggregation="document_count",
                aggregation_name="_bucket_doc_count",
                aggregation_result_path="doc_count",
                aggregation_semantics="additive",
            ),
            *(
                column
                for specification in query.semantics.field_measures
                for column in self._measure_columns(specification)
            ),
            DatasetColumn(
                name="raw_metrics",
                data_type="metric",
                nullable=True,
                semantic_role="metadata",
            ),
        )
        output_dataset_id = safe_identifier(dataset_id or f"{query.step_id}_base")
        payload = {
            "dataset_id": output_dataset_id,
            "grain": dimensions,
            "dimensions": dimensions,
            "metrics": query.semantics.metric_ids,
            "measures": tuple(item.measure_id for item in query.semantics.field_measures),
            "primary_key": dimensions,
            "expected_complete_dimensions": dimensions,
            "columns": [item.model_dump(mode="json") for item in columns],
            "bucket_path": [item.model_dump(mode="json") for item in query.semantics.bucket_path],
        }
        return DatasetContract(
            object_id=query.result_contract_id,
            created_at=datetime.now(UTC),
            content_hash=semantic_hash(payload),
            provenance=Provenance(
                producer="analytics.dataset_contract_factory",
                source_ids=(query.object_id,),
            ),
            dataset_id=output_dataset_id,
            grain=dimensions,
            dimensions=dimensions,
            metrics=query.semantics.metric_ids,
            measures=tuple(item.measure_id for item in query.semantics.field_measures),
            primary_key=dimensions,
            expected_complete_dimensions=dimensions,
            columns=columns,
            bucket_path=query.semantics.bucket_path,
        )

    @staticmethod
    def _measure_columns(specification: AggregationSpec) -> tuple[DatasetColumn, ...]:
        paths: tuple[str, ...]
        if specification.aggregation in {AggregationKind.STATS, AggregationKind.EXTENDED_STATS}:
            paths = tuple(name.rsplit("_", 1)[-1] for name in specification.output_columns)
            if specification.aggregation == AggregationKind.EXTENDED_STATS:
                paths = (
                    "count",
                    "min",
                    "max",
                    "avg",
                    "sum",
                    "sum_of_squares",
                    "variance",
                    "std_deviation",
                )
        elif specification.aggregation == AggregationKind.PERCENTILES:
            percents = specification.parameters.percents or (50.0, 95.0, 99.0)
            paths = tuple(f"values.{percent:g}" for percent in percents)
        else:
            paths = ("value",)
        return tuple(
            DatasetColumn(
                name=name,
                data_type=(
                    "integer"
                    if specification.aggregation
                    in {AggregationKind.VALUE_COUNT, AggregationKind.CARDINALITY}
                    or path == "count"
                    else "number"
                ),
                nullable=True,
                semantic_role="measure",
                measure_id=specification.measure_id,
                source_field_id=specification.source_field_id,
                aggregation=specification.aggregation.value,
                aggregation_name=specification.aggregation_name,
                aggregation_result_path=path,
                aggregation_parameters=specification.parameters.model_dump(mode="json"),
                aggregation_semantics=specification.semantics.value,
                unit=specification.unit,
                approximate=specification.approximate,
            )
            for name, path in zip(specification.output_columns, paths, strict=True)
        )
