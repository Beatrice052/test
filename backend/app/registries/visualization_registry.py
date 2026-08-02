"""Safe visualization intent registry."""

from pathlib import Path

from app.contracts.dashboard import VisualizationDefinition
from app.registries.base import iter_yaml_files, load_yaml, normalize_items, unique_index


class VisualizationRegistry:
    def __init__(self, definitions: tuple[VisualizationDefinition, ...]) -> None:
        self.definitions = definitions
        self.by_id = unique_index(definitions, key="visualization_id")

    @classmethod
    def load(cls, path: Path) -> "VisualizationRegistry":
        definitions: list[VisualizationDefinition] = []
        for file_path in iter_yaml_files(path):
            definitions.extend(
                VisualizationDefinition.model_validate(item, strict=False)
                for item in normalize_items(load_yaml(file_path), container_key="visualizations")
            )
        return cls(tuple(definitions))
