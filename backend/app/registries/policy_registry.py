"""Policy registry; policy can only reduce Mapping capabilities."""

from pathlib import Path

from app.contracts.semantic import PolicyDefinition
from app.registries.base import load_yaml, normalize_items, unique_index


class PolicyRegistry:
    def __init__(self, definitions: tuple[PolicyDefinition, ...]) -> None:
        self.definitions = definitions
        self.by_id = unique_index(definitions, key="policy_id")

    @classmethod
    def load(cls, path: Path) -> "PolicyRegistry":
        items = normalize_items(load_yaml(path), container_key="policies")
        return cls(tuple(PolicyDefinition.model_validate(item, strict=False) for item in items))
