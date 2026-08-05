"""Governed field-level measure registry."""

from pathlib import Path

from app.contracts.metric import MeasureDefinition
from app.registries.base import iter_yaml_files, load_yaml, normalize_items


class MeasureRegistry:
    def __init__(self, definitions: tuple[MeasureDefinition, ...]) -> None:
        self.definitions = definitions
        self.by_versioned_id: dict[str, MeasureDefinition] = {}
        for definition in definitions:
            if definition.versioned_id in self.by_versioned_id:
                raise ValueError(f"duplicate measure: {definition.versioned_id}")
            self.by_versioned_id[definition.versioned_id] = definition

    @classmethod
    def load(cls, path: Path) -> "MeasureRegistry":
        if not path.exists():
            return cls(())
        definitions: list[MeasureDefinition] = []
        for file_path in iter_yaml_files(path):
            definitions.extend(
                MeasureDefinition.model_validate(item, strict=False)
                for item in normalize_items(load_yaml(file_path), container_key="measures")
            )
        return cls(tuple(definitions))
