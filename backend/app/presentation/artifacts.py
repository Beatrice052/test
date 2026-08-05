"""Content-addressed Evidence artifact storage with bounded, owner-mediated reads."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from app.contracts.common import canonical_json
from app.persistence.ids import new_id

ARTIFACT_ID = re.compile(r"^art_[a-z0-9-]{20,127}$")


class EvidenceArtifactError(ValueError):
    pass


class EvidenceArtifactStore:
    """Store only governed Evidence payloads; authorization is enforced via Answer ownership."""

    def __init__(self, root: Path, *, maximum_bytes: int = 10_000_000) -> None:
        self.root = (root / "evidence").resolve()
        self.maximum_bytes = maximum_bytes
        self.root.mkdir(parents=True, exist_ok=True)

    def write_json(self, payload: Any) -> tuple[str, str, int]:
        content = (canonical_json(payload) + "\n").encode("utf-8")
        if len(content) > self.maximum_bytes:
            raise EvidenceArtifactError(
                f"evidence artifact exceeds configured limit: {len(content)} bytes"
            )
        artifact_id = new_id("art")
        digest = f"sha256:{hashlib.sha256(content).hexdigest()}"
        path = self._path(artifact_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_bytes(content)
        temporary.replace(path)
        return artifact_id, digest, len(content)

    def read_json(self, artifact_id: str, *, expected_hash: str) -> bytes:
        path = self._path(artifact_id)
        try:
            content = path.read_bytes()
        except OSError as error:
            raise EvidenceArtifactError("evidence artifact is unavailable") from error
        if len(content) > self.maximum_bytes:
            raise EvidenceArtifactError("stored evidence artifact exceeds configured limit")
        digest = f"sha256:{hashlib.sha256(content).hexdigest()}"
        if digest != expected_hash:
            raise EvidenceArtifactError("evidence artifact hash mismatch")
        try:
            json.loads(content)
        except json.JSONDecodeError as error:
            raise EvidenceArtifactError("evidence artifact is not valid JSON") from error
        return content

    def _path(self, artifact_id: str) -> Path:
        if ARTIFACT_ID.fullmatch(artifact_id) is None:
            raise EvidenceArtifactError("invalid evidence artifact ID")
        path = (self.root / artifact_id[:12] / f"{artifact_id}.json").resolve()
        if self.root not in path.parents:
            raise EvidenceArtifactError("evidence artifact path escaped its root")
        return path
