"""Small deterministic YAML registry loader utilities."""

from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel


class RegistryLoadError(ValueError):
    pass


def load_yaml(path: Path) -> Any:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return yaml.safe_load(handle)
    except (OSError, yaml.YAMLError) as error:
        raise RegistryLoadError(f"cannot load registry file {path}: {error}") from error


def iter_yaml_files(path: Path) -> Iterable[Path]:
    if path.is_file():
        yield path
        return
    if not path.exists():
        raise RegistryLoadError(f"registry path does not exist: {path}")
    yield from sorted((*path.glob("*.yaml"), *path.glob("*.yml")))


def normalize_items(raw: Any, *, container_key: str) -> list[Mapping[str, Any]]:
    if isinstance(raw, Mapping) and container_key in raw:
        raw = raw[container_key]
    if isinstance(raw, Mapping):
        return [raw]
    if isinstance(raw, list) and all(isinstance(item, Mapping) for item in raw):
        return list(raw)
    raise RegistryLoadError(f"registry must contain an object or list under {container_key}")


def unique_index[ModelT: BaseModel](items: Iterable[ModelT], *, key: str) -> dict[str, ModelT]:
    indexed: dict[str, ModelT] = {}
    for item in items:
        item_key = str(getattr(item, key))
        if item_key in indexed:
            raise RegistryLoadError(f"duplicate registry key: {item_key}")
        indexed[item_key] = item
    return indexed
