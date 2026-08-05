"""Governed metric, value dictionary, formula, and method contracts."""

from enum import StrEnum
from typing import Literal

from pydantic import Field

from app.contracts.common import Identifier, JsonScalar, StrictModel


class MetricLevel(StrEnum):
    CERTIFIED = "CERTIFIED"
    GOVERNED_DERIVED = "GOVERNED_DERIVED"
    EXPLORATORY = "EXPLORATORY"
    UNSUPPORTED = "UNSUPPORTED"


class AggregationKind(StrEnum):
    DOCUMENT_COUNT = "document_count"
    VALUE_COUNT = "value_count"
    CARDINALITY = "cardinality"
    SUM = "sum"
    AVG = "avg"
    MIN = "min"
    MAX = "max"
    STATS = "stats"
    EXTENDED_STATS = "extended_stats"
    PERCENTILES = "percentiles"


class AggregationSemantics(StrEnum):
    ADDITIVE = "additive"
    SEMI_ADDITIVE = "semi_additive"
    NON_ADDITIVE = "non_additive"
    WEIGHTED = "weighted"


class AggregationParameters(StrictModel):
    percents: tuple[float, ...] = ()
    precision_threshold: int | None = Field(default=None, ge=0, le=40000)
    sigma: float | None = Field(default=None, ge=0, le=10)
    keyed: bool = True

    def model_post_init(self, __context: object) -> None:
        if any(percent < 0 or percent > 100 for percent in self.percents):
            raise ValueError("percentiles must be between 0 and 100")
        if len(self.percents) != len(set(self.percents)):
            raise ValueError("percentiles must be unique")


class AggregationSpec(StrictModel):
    """A logical, governed field aggregation. It never contains a physical path."""

    measure_id: Identifier
    source_field_id: Identifier | None = None
    aggregation: AggregationKind
    parameters: AggregationParameters = Field(default_factory=AggregationParameters)
    unit: str = "number"
    semantics: AggregationSemantics = AggregationSemantics.NON_ADDITIVE
    approximate: bool = False

    def model_post_init(self, __context: object) -> None:
        if self.aggregation != AggregationKind.DOCUMENT_COUNT and self.source_field_id is None:
            raise ValueError("field aggregation requires source_field_id")
        if self.aggregation != AggregationKind.PERCENTILES and self.parameters.percents:
            raise ValueError("percents are only valid for percentile aggregations")
        if (
            self.aggregation != AggregationKind.CARDINALITY
            and self.parameters.precision_threshold is not None
        ):
            raise ValueError("precision_threshold is only valid for cardinality")
        if self.aggregation != AggregationKind.EXTENDED_STATS and self.parameters.sigma is not None:
            raise ValueError("sigma is only valid for extended_stats")

    @property
    def aggregation_name(self) -> str:
        base = self.measure_id.replace(".", "_").replace("-", "_")
        return f"measure_{base}_{self.aggregation.value}"

    @property
    def output_columns(self) -> tuple[str, ...]:
        base = self.aggregation_name.removeprefix("measure_")
        if self.aggregation == AggregationKind.STATS:
            return tuple(f"{base}_{name}" for name in ("count", "min", "max", "avg", "sum"))
        if self.aggregation == AggregationKind.EXTENDED_STATS:
            return tuple(
                f"{base}_{name}"
                for name in (
                    "count",
                    "min",
                    "max",
                    "avg",
                    "sum",
                    "sum_of_squares",
                    "variance",
                    "std_deviation",
                )
            )
        if self.aggregation == AggregationKind.PERCENTILES:
            percents = self.parameters.percents or (50.0, 95.0, 99.0)
            return tuple(f"{base}_p{percent:g}".replace(".", "_") for percent in percents)
        return (base,)


class MeasureDefinition(StrictModel):
    """Config-only definition of a governed aggregation over one semantic field."""

    measure_id: Identifier
    version: str = Field(pattern=r"^v[1-9][0-9]*$")
    display_name: str
    business_definition: str
    source_field_id: Identifier | None = None
    allowed_aggregations: tuple[AggregationKind, ...] = Field(min_length=1)
    default_aggregation: AggregationKind
    default_parameters: AggregationParameters = Field(default_factory=AggregationParameters)
    unit: str = "number"
    source_grain: tuple[Identifier, ...] = ()
    population_scope: str = "filtered_documents"
    semantics: AggregationSemantics = AggregationSemantics.NON_ADDITIVE
    approximate: bool = False
    owner: str | None = None
    enabled: bool = True

    @property
    def versioned_id(self) -> str:
        return f"{self.measure_id}.{self.version}"

    def model_post_init(self, __context: object) -> None:
        if self.default_aggregation not in self.allowed_aggregations:
            raise ValueError("default aggregation must be allowlisted")
        if not self.allowed_aggregations:
            raise ValueError("measure requires at least one allowed aggregation")
        if (
            any(kind != AggregationKind.DOCUMENT_COUNT for kind in self.allowed_aggregations)
            and self.source_field_id is None
        ):
            raise ValueError("field measures require source_field_id")

    def aggregation_spec(
        self,
        aggregation: AggregationKind | None = None,
        parameters: AggregationParameters | None = None,
    ) -> AggregationSpec:
        selected = aggregation or self.default_aggregation
        if selected not in self.allowed_aggregations:
            raise ValueError(f"aggregation is not allowed for {self.versioned_id}: {selected}")
        return AggregationSpec(
            measure_id=self.versioned_id,
            source_field_id=self.source_field_id,
            aggregation=selected,
            parameters=parameters or self.default_parameters,
            unit=self.unit,
            semantics=self.semantics,
            approximate=self.approximate or selected == AggregationKind.CARDINALITY,
        )


class FormulaNode(StrictModel):
    operator: Literal[
        "constant",
        "column",
        "filtered_count",
        "add",
        "subtract",
        "multiply",
        "divide",
        "sum",
    ]
    value: float | None = None
    column: str | None = None
    status_groups: tuple[str, ...] = ()
    operands: tuple["FormulaNode", ...] = ()

    def model_post_init(self, __context: object) -> None:
        if self.operator == "constant" and self.value is None:
            raise ValueError("constant formula requires value")
        if self.operator == "column" and self.column is None:
            raise ValueError("column formula requires column")
        if self.operator == "filtered_count" and not self.status_groups:
            raise ValueError("filtered_count requires status_groups")
        if self.operator in {"add", "subtract", "multiply", "divide", "sum"} and not self.operands:
            raise ValueError(f"{self.operator} requires operands")


class MetricTimeSemantics(StrictModel):
    capability_id: Identifier
    timezone: str


class MetricDefinition(StrictModel):
    metric_id: Identifier
    version: str = Field(pattern=r"^v[1-9][0-9]*$")
    level: MetricLevel
    display_name: str
    business_definition: str
    numerator: FormulaNode | None = None
    denominator: FormulaNode | None = None
    formula: FormulaNode | None = None
    time_semantics: MetricTimeSemantics | None = None
    dimensions: tuple[Identifier, ...] = ()
    null_policy: str = "exclude_and_report"
    pending_policy: str = "exclude"
    unknown_policy: str = "exclude_and_report"
    minimum_denominator: int = Field(default=0, ge=0)
    unit: Literal["count", "ratio", "milliseconds", "number"] = "number"
    precision: int = Field(default=4, ge=0, le=12)
    source_field_ids: tuple[Identifier, ...] = ()
    value_dictionary_ids: tuple[Identifier, ...] = ()
    aggregation_semantics: AggregationSemantics = AggregationSemantics.NON_ADDITIVE
    approximate: bool = False
    owner: str | None = None
    enabled: bool = True

    @property
    def versioned_id(self) -> str:
        return f"{self.metric_id}.{self.version}"

    def model_post_init(self, __context: object) -> None:
        ratio_parts = self.numerator is not None or self.denominator is not None
        if ratio_parts and (self.numerator is None or self.denominator is None):
            raise ValueError("ratio metric requires both numerator and denominator")
        if ratio_parts and self.formula is not None:
            raise ValueError("use numerator/denominator or formula, not both")
        if not ratio_parts and self.formula is None:
            raise ValueError("metric requires formula or numerator/denominator")


class MetricValue(StrictModel):
    metric_id: Identifier
    metric_version: str
    value: float | int | None
    unit: str
    numerator: float | int | None = None
    denominator: float | int | None = None
    excluded: dict[str, int] = Field(default_factory=dict)
    quality: Literal["VALID", "INSUFFICIENT_SAMPLE", "INVALID", "NOT_APPLICABLE"]
    approximate: bool = False
    evidence_row_ids: tuple[str, ...] = ()


class ValueDictionary(StrictModel):
    dictionary_id: Identifier
    version: str
    source_field_id: Identifier
    values: dict[str, str]
    null_group: str
    owner: str | None = None


class MethodDefinition(StrictModel):
    method_id: Identifier
    version: str
    display_name: str
    purpose: str = "Governed deterministic statistical analysis"
    technical_description: str = "Computed by the host from validated tabular data."
    minimum_rows: int = Field(ge=0)
    required_semantic_types: tuple[str, ...] = ()
    exploratory_label_required: bool = True
    default_params: dict[str, JsonScalar] = Field(default_factory=dict)
    parameter_limits: dict[str, JsonScalar] = Field(default_factory=dict)
    supported_partition_roles: tuple[str, ...] = ()
    requires_category: bool = False
    requires_time: bool = False
    interpretation_limitations: tuple[str, ...] = ()


class AnalysisRecipe(StrictModel):
    recipe_id: Identifier
    version: str
    question_archetype: str
    metric_ids: tuple[Identifier, ...] = ()
    measure_ids: tuple[Identifier, ...] = ()
    method_ids: tuple[Identifier, ...] = ()
    dimension_roles: tuple[str, ...] = ()
    visualization_intents: tuple[str, ...] = ()
    minimum_capabilities: tuple[str, ...] = ()
