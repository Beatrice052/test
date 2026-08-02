"""Value dictionary registry."""

from pathlib import Path

from app.contracts.metric import ValueDictionary
from app.registries.base import iter_yaml_files, load_yaml, normalize_items, unique_index


class ValueRegistry:
    def __init__(self, definitions: tuple[ValueDictionary, ...]) -> None:
        self.definitions = definitions
        self.by_id = unique_index(definitions, key="dictionary_id")

    @classmethod
    def load(cls, path: Path) -> "ValueRegistry":
        definitions: list[ValueDictionary] = []
        for file_path in iter_yaml_files(path):
            for item in normalize_items(load_yaml(file_path), container_key="dictionaries"):
                definitions.append(ValueDictionary.model_validate(item, strict=False))
        return cls(tuple(definitions))
