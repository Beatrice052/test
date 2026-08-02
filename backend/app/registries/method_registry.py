"""Exploratory statistical method registry."""

from pathlib import Path

from app.contracts.metric import MethodDefinition
from app.registries.base import iter_yaml_files, load_yaml, normalize_items, unique_index


class MethodRegistry:
    def __init__(self, definitions: tuple[MethodDefinition, ...]) -> None:
        self.definitions = definitions
        self.by_id = unique_index(definitions, key="method_id")

    @classmethod
    def load(cls, path: Path) -> "MethodRegistry":
        definitions: list[MethodDefinition] = []
        for file_path in iter_yaml_files(path):
            definitions.extend(
                MethodDefinition.model_validate(item, strict=False)
                for item in normalize_items(load_yaml(file_path), container_key="methods")
            )
        return cls(tuple(definitions))
