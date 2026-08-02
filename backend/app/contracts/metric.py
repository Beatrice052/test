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
    minimum_rows: int = Field(ge=0)
    required_semantic_types: tuple[str, ...] = ()
    exploratory_label_required: bool = True
    default_params: dict[str, JsonScalar] = Field(default_factory=dict)


class AnalysisRecipe(StrictModel):
    recipe_id: Identifier
    version: str
    question_archetype: str
    metric_ids: tuple[Identifier, ...] = ()
    method_ids: tuple[Identifier, ...] = ()
    dimension_roles: tuple[str, ...] = ()
    visualization_intents: tuple[str, ...] = ()
    minimum_capabilities: tuple[str, ...] = ()
