"""Analysis recipe registry."""

from pathlib import Path

from app.contracts.metric import AnalysisRecipe
from app.registries.base import iter_yaml_files, load_yaml, normalize_items, unique_index


class RecipeRegistry:
    def __init__(self, definitions: tuple[AnalysisRecipe, ...]) -> None:
        self.definitions = definitions
        self.by_id = unique_index(definitions, key="recipe_id")

    @classmethod
    def load(cls, path: Path) -> "RecipeRegistry":
        definitions: list[AnalysisRecipe] = []
        for file_path in iter_yaml_files(path):
            definitions.extend(
                AnalysisRecipe.model_validate(item, strict=False)
                for item in normalize_items(load_yaml(file_path), container_key="recipes")
            )
        return cls(tuple(definitions))
