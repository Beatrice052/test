"""Dataset registry."""

from pathlib import Path

from app.contracts.semantic import DatasetDefinition
from app.registries.base import load_yaml, normalize_items, unique_index


class DatasetRegistry:
    def __init__(self, definitions: tuple[DatasetDefinition, ...]) -> None:
        self.definitions = definitions
        self.by_id = unique_index(definitions, key="dataset_id")

    @classmethod
    def load(cls, path: Path) -> "DatasetRegistry":
        items = normalize_items(load_yaml(path), container_key="datasets")
        return cls(tuple(DatasetDefinition.model_validate(item, strict=False) for item in items))
