"""Governed entity and member-resolution registry."""

from pathlib import Path

from app.contracts.semantic import EntityDefinition
from app.registries.base import iter_yaml_files, load_yaml, normalize_items


class EntityRegistry:
    def __init__(self, definitions: tuple[EntityDefinition, ...]) -> None:
        self.definitions = definitions
        self.by_versioned_id: dict[str, EntityDefinition] = {}
        for definition in definitions:
            if definition.versioned_id in self.by_versioned_id:
                raise ValueError(f"duplicate entity: {definition.versioned_id}")
            self.by_versioned_id[definition.versioned_id] = definition

    @classmethod
    def load(cls, path: Path) -> "EntityRegistry":
        if not path.exists():
            return cls(())
        definitions: list[EntityDefinition] = []
        for file_path in iter_yaml_files(path):
            definitions.extend(
                EntityDefinition.model_validate(item, strict=False)
                for item in normalize_items(load_yaml(file_path), container_key="entities")
            )
        return cls(tuple(definitions))
